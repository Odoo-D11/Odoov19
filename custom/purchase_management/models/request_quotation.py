from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain as expression
from markupsafe import Markup
from ..utils.utils import format_html_to_sentence_case, convert_first_letter_to_uppercase, _build_excel_file_supplier, _clean_note_text, _show_error_notification
from datetime import timedelta
import unicodedata
import xmlrpc.client


class RequestQuotation(models.Model):
    _name = "request.quotation"
    _description = "Solicitud"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'purchase.board.mixin']
    _rec_name = "reference"
    _order = "reference asc"

    """ONE2MANY"""
    product_line_ids = fields.One2many(
        "request.product.quotation.line", "request_quotation_id", string="Productos solicitados")
    quotation_line_ids = fields.One2many(
        "quotation.quotation", "request_quotation_id", string="Cotizaciones")
    additional_info_ids = fields.One2many(
        "purchase.additional.information", "request_quotation_id", string="Información adicional", readonly=True)
    purchase_order_ids = fields.One2many(
        "purchase.management.order", "request_quotation_id", string="Órdenes de compra asociadas", readonly=True)
    """MANY2MANY"""
    technical_spec_attachment_ids = fields.Many2many(
        'ir.attachment',
        'request_quotation_technical_spec_rel',
        'request_quotation_id',
        'attachment_id',
        string='Fichas Técnicas',
    )
    """MANY2ONE"""
    type_id = fields.Many2one(
        "request.type", string="Tipo de Solicitud", required=True, domain="[('name', 'in', ['Productos', 'Servicios'])]")
    project_id = fields.Many2one(
        "project.management", string="Proyecto", required=True, domain="[('category_id', '!=', False)]")
    responsible_id = fields.Many2one(
        "hr.employee", string="Responsable", required=True)
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True, default=lambda self: self.env.company.currency_id, readonly=True)
    responsible_purchase_id = fields.Many2one(
        "purchase.member", string="Responsable de Compras", domain="[('team_id.name', '=', 'Compras')]", readonly=True)
    """SELECTION"""
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('in_shopping', 'En Compras'),
        ('returned', 'Devuelta'),
        ('sent', 'Enviado'),
        ('pending_project_approval', 'Pendiente de Aprobación del Gerente de Proyecto'),
        ('pending_purchase_approval', 'Pendiente de Aprobación de Compras'),
        ('pending_advisory_committee_approval',
         'Pendiente de Aprobación del Comité de Compras'),
        ('approved', 'Aprobado'),
        ('order_created', 'Orden Creada'),
        ('cancelled', 'Cancelado'),
    ], string="Estado", default='draft')
    category = fields.Selection([
        ('project', 'Proyecto'),
        ('admin', 'Administrativo'),
    ], string="Categoría", compute='_compute_category', store=True,)
    """INTEGER"""
    min_providers_qty = fields.Integer(
        string='Nro. mínimo de proveedores', readonly=True,
        default=lambda self: self.env['ir.config_parameter'].sudo().get_param(
            'purchase_management.min_providers_qty', default=3),
        help='Indica el número mínimo de proveedores según política corporativa.'
    )
    """CHAR"""
    subject = fields.Char(string="Asunto", required=True)
    reference = fields.Char(string="Referencia", required=True, copy=False,
                            readonly=True, index=True, default=lambda self: _('Nueva'))
    """DATE"""
    create_date = fields.Date(string="Fecha de creación", readonly=True)
    deadline = fields.Date(string="Fecha límite", required=True)
    close_date = fields.Date(string="Fecha de cierre", readonly=True)
    days_remaining = fields.Integer(
        string="Días restantes",
        compute='_compute_days_remaining',
    )
    """TEXT"""
    reason = fields.Text(string="Motivo de la solicitud", required=True)
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True, readonly=True)
    is_min_providers_approval_pending = fields.Boolean(
        string='Pendiente aprobación (mínimo de proveedores)', default=False, readonly=True,
        help='Indica si requiere aprobación por tener menos proveedores del mínimo.')
    all_quotation_rejected = fields.Boolean(
        string='Todas las cotizaciones rechazadas', default=False, readonly=True)
    commitee_approval_rejected = fields.Boolean(
        string='Rechazo de aprobación del comité', default=False, readonly=True)
    rejected_by_project_leader = fields.Boolean(
        string='Rechazo de aprobación del lider de proyecto', default=False, readonly=True,
        help='Indica que el lider de proyecto ha rechazado alguna cotización de la solicitud')
    pause_request = fields.Boolean(
        string='Solicitud pausada', readonly=True, default=False)
    locked = fields.Boolean(string='Bloqueado', default=False, readonly=True, copy=False)

    def action_lock(self):
        self._check_lock_permission()
        self.locked = True

    def action_unlock(self):
        self._check_lock_permission()
        self.locked = False

    def _check_lock_permission(self):
        is_unlock = self.env.user.has_group(
            'purchase_management.group_unlock_request_quotation')
        is_admin = self.env.user.has_group(
            'purchase_management.group_manager_purchase_management')
        if not (is_unlock or is_admin):
            raise UserError(
                _('Solo un usuario con permiso "Desbloqueo de SDC" o Administrador puede bloquear/desbloquear esta solicitud.'))

    @api.depends('deadline')
    def _compute_days_remaining(self):
        today = fields.Date.today()
        for rec in self:
            rec.days_remaining = (
                rec.deadline - today).days if rec.deadline else 999

    @api.depends('project_id')
    def _compute_category(self):
        for record in self:
            is_project = record.project_id and record.project_id.category_id.name == 'Proyecto'
            record.category = 'project' if is_project else 'admin' if record.project_id else False

    def _check_category(self):
        if any(record.category not in ('project', 'admin') for record in self):
            raise ValidationError(
                _('No se pudo determinar la categoría de la solicitud. Por favor, comuniquese con el administrador del sistema.'))

    @api.model
    def get_avatar_widget_config(self, record_id=False, field_name=False):
        if field_name != "responsible_id":
            return {}
        return {
            "channel_name": f"request_quotation_avatar_{record_id}" if record_id else False,
            "notification_type": "purchase.avatar/update",
            "payload_key": "quotation_id",
        }

    def _prepare_avatar_payload(self, reason, timestamp, payload_key):
        self.ensure_one()
        employee = self.responsible_id
        payload = {
            "quotation_id": self.id,
            "employee_id": employee.id if employee else False,
            "reason": reason,
            "timestamp": timestamp,
        }
        if payload_key and payload_key not in payload:
            payload[payload_key] = self.id
        return payload

    def _notify_avatar_update(self, reason="update"):
        """Notifica al frontend para que actualice la información del avatar."""
        records = self.filtered('id')
        if not records:
            return
        timestamp = fields.Datetime.now()
        bus = self.env['bus.bus']
        for record in records:
            config = self.get_avatar_widget_config(record.id, "responsible_id")
            channel = config.get("channel_name")
            if not channel:
                continue
            payload = record._prepare_avatar_payload(
                reason, timestamp, config.get("payload_key", "record_id"))
            bus._sendone(channel, config.get(
                "notification_type", "avatar/update"), payload)

    @api.model
    def _cron_cleanup_xlsx_attachments(self, batch_size=200):
        """Elimina los archivos adjuntos .XLSX de request.quotation antiguos,
        no cuenta los que aun estan en wizards activos o por correos 
        pendientes de envio."""
        domain = [
            ('res_model', 'in', ['request.quotation',
             'purchase.send.mail.wizard']),
            ('mimetype', '=', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('name', 'ilike', '.xlsx'),
        ]
        attachments = self.env['ir.attachment'].sudo().search(
            domain, limit=batch_size)
        if not attachments:
            return

        # Los attachments que aun estan vinculados a un wizard
        self.env.cr.execute("""
            SELECT DISTINCT wrel.ir_attachment_id
            FROM purchase_send_mail_wizard_ir_attachment_rel wrel
            JOIN purchase_send_mail_wizard w ON w.id = wrel.purchase_send_mail_wizard_id
            WHERE wrel.ir_attachment_id IN %s
        """, [tuple(attachments.ids)])
        wizard_ids = {row[0] for row in self.env.cr.fetchall()}

        # Los attachments que estan en mail.mail que aun no se han enviado ni cancelado
        self.env.cr.execute("""
            SELECT DISTINCT rel.attachment_id
            FROM message_attachment_rel rel
            JOIN mail_mail mm ON mm.mail_message_id = rel.message_id
            WHERE rel.attachment_id IN %s
              AND mm.state NOT IN ('sent', 'cancel')
        """, [tuple(attachments.ids)])
        pending_ids = {row[0] for row in self.env.cr.fetchall()}

        protected_ids = wizard_ids | pending_ids
        safe_to_delete = attachments.filtered(
            lambda a: a.id not in protected_ids)
        safe_to_delete.unlink()

    @api.model
    def default_get(self, default_fields):
        vals = super(RequestQuotation, self).default_get(default_fields)
        vals['responsible_id'] = self.env.user.employee_id.id if self.env.user.employee_id else False
        return vals

    @api.onchange('reason')
    def _onchange_reason(self):
        for record in self:
            if record.reason:
                record.reason = _clean_note_text(record.reason)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reason'):
                vals['reason'] = _clean_note_text(vals['reason'])
            if vals.get('subject'):
                vals['subject'] = convert_first_letter_to_uppercase(
                    vals['subject'])
        records = super().create(vals_list)
        if records:
            if records.category == 'admin':
                records.reference = self.env['ir.sequence'].next_by_code(
                    'administrative.request') or _('Nueva')
            records._notify_avatar_update(reason="create")
        return records

    def write(self, vals):
        previous_responsibles = {
            rec.id: rec.responsible_id.id for rec in self} if 'responsible_id' in vals else {}
        if vals.get('reason'):
            vals['reason'] = _clean_note_text(vals['reason'])
        if vals.get('subject'):
            vals['subject'] = convert_first_letter_to_uppercase(
                vals['subject'])
        _editable_when_locked = {
            'locked', 'message_ids', 'message_follower_ids', 'activity_ids'
        }
        is_unlock = self.env.user.has_group(
            'purchase_management.group_unlock_request_quotation')
        is_admin = self.env.user.has_group(
            'purchase_management.group_manager_purchase_management')
        is_privileged = is_unlock or is_admin

        for record in self:
            if record.locked:
                if not is_privileged:
                    raise UserError(
                        _('La solicitud está bloqueada. Solo un usuario con permiso "Desbloqueo de SDC" o Administrador puede desbloquearla.'))
                if not (set(vals.keys()) <= _editable_when_locked):
                    raise UserError(
                        _('La solicitud está bloqueada. Desbloquéala antes de realizar cambios.'))

        if not is_privileged:
            self._check_editable_fields(vals)
        res = super().write(vals)
        if res and 'product_line_ids' in vals:
            self._validate_unique_product_names()
            self._validate_products_have_specifications()
        if res and 'responsible_id' in vals:
            changed = self.filtered(
                lambda r: previous_responsibles.get(r.id) != r.responsible_id.id)
            if changed:
                changed._notify_avatar_update(reason="write")
        return res

    def unlink(self):
        if any(rec.state not in ('draft') for rec in self) and not self.env.user.has_group('purchase_management.group_manager_purchase_management'):
            raise UserError(
                _('Solo se pueden eliminar las solicitudes en estado "Borrador".'))
        return super().unlink()

    def _check_editable_fields(self, vals):
        non_editable = {'responsible_id', 'deadline', 'project_id',
                        'type_id', 'subject', 'reason', 'product_line_ids'}
        forbidden_keys = non_editable.intersection(vals.keys())
        if forbidden_keys and any(rec.state not in ('draft', 'returned') for rec in self):
            field_name = self._fields[list(forbidden_keys)[0]].string
            state_label = dict(
                self._fields['state'].selection).get(self[0].state)
            raise UserError(
                _('No se puede modificar "%s" en estado "%s". Solo en "Borrador".') % (
                    field_name, state_label)
            )

    @api.constrains('type_id')
    def _check_type_id(self):
        for record in self:
            if record.state != 'draft' and record.type_id != record._origin.type_id:
                raise ValidationError(
                    _('No se puede cambiar el tipo de solicitud fuera del estado "Borrador".'))

    def _validate_unique_product_names(self):
        """Valida que productos con el mismo nombre tengan especificaciones diferentes"""
        for record in self:
            # Ordena las líneas por secuencia para emparejar productos con sus notas
            sorted_lines = list(record.product_line_ids.sorted('sequence'))
            # Crea la lista de tuplas (nombre_producto, especificacion) usando secuencia
            product_spec_pairs = []
            i = 0
            while i < len(sorted_lines):
                line = sorted_lines[i]
                if line.display_type != 'line_note':
                    # Es un producto, buscar su nota por posición (línea inmediata siguiente)
                    spec_text = ''
                    if i + 1 < len(sorted_lines):
                        next_line = sorted_lines[i + 1]
                        if next_line.display_type == 'line_note':
                            spec_text = (next_line.name or '').strip().lower()
                            i += 1  # Saltar la nota ya procesada
                    product_spec_pairs.append((line.name, spec_text))
                i += 1

            # Verifica que no haya pares (nombre, especificación) duplicados
            seen_pairs = set()
            for name, spec in product_spec_pairs:
                pair = (name.strip().lower(), spec)
                if pair in seen_pairs:
                    raise ValidationError(
                        _('El producto "%s" está duplicado y tiene la misma especificación. '
                          'Los productos duplicados deben tener especificaciones diferentes.') % name
                    )
                seen_pairs.add(pair)

    def _validate_products_have_specifications(self):
        """Valida que cada producto tenga exactamente una especificación (nota) asociada"""
        for record in self:
            # Ordena las líneas por secuencia
            sorted_lines = list(record.product_line_ids.sorted('sequence'))
            # Validar estructura: cada producto debe tener su nota inmediatamente después
            i = 0
            while i < len(sorted_lines):
                line = sorted_lines[i]
                if line.display_type != 'line_note':
                    # Es un producto, verificar que la siguiente línea sea su nota
                    if i + 1 >= len(sorted_lines):
                        raise ValidationError(
                            _('El producto "%s" no tiene una especificación asociada.') % line.name
                        )

                    next_line = sorted_lines[i + 1]
                    if next_line.display_type != 'line_note':
                        raise ValidationError(
                            _('El producto "%s" no tiene una especificación asociada.') % line.name
                        )

                    if (next_line.product_name or '').strip().lower() != (line.name or '').strip().lower():
                        raise ValidationError(
                            _('La especificación después del producto "%s" está asociada a otro producto ("%s").') % (
                                line.name, next_line.product_name)
                        )

                    if not (next_line.name or '').strip():
                        raise ValidationError(
                            _('La especificación del producto "%s" no puede estar vacía.') % line.name
                        )

                    i += 2  # Salta el producto y su nota
                else:
                    # Es una nota sin producto previo
                    raise ValidationError(
                        _('Existe una especificación asociada al producto "%s", pero ese producto no se encuentra antes de ella en la lista.') % line.product_name
                    )

    @api.model
    def get_board_data(self, request_quotation_id):
        """Endpoint que retorna datos para ProductBoard y QuotationBoard en una sola llamada RPC."""
        if not request_quotation_id:
            return {'products': [], 'quotations': [], 'quotation_products': []}

        products = self.env['request.product.quotation.line'].search_read(
            [('request_quotation_id', '=', request_quotation_id)],
            ['id', 'qty', 'display_type'],
        )

        quotations = self.env['quotation.quotation'].search_read(
            [('request_quotation_id', '=', request_quotation_id)],
            ['id', 'write_date', 'product_line_ids', 'supplier_name',
             'validity_date', 'delivery_date', 'payment_term',
             'currency_id', 'observation_ids', 'trm',
             'purchase_observation_recommendation_ids'],
        )

        all_line_ids = []
        for q in quotations:
            all_line_ids.extend(q.get('product_line_ids', []))

        quotation_products = []
        if all_line_ids:
            quotation_products = self.env['product.quotation.line'].search_read(
                [('id', 'in', all_line_ids)],
                ['id', 'name', 'subtotal', 'display_type'],
            )

        return {
            'products': products,
            'quotations': quotations,
            'quotation_products': quotation_products,
        }

    @api.model
    def get_board_update_hash(self, request_quotation_id):
        """Endpoint ligero para polling: retorna un hash basado en write_dates y counts
        para que los widgets puedan verificar si hay cambios sin cargar datos completos."""
        if not request_quotation_id:
            return {'hash': ''}

        self.env.cr.execute("""
            SELECT
                COALESCE(COUNT(*), 0) AS product_count,
                COALESCE(MAX(write_date)::text, '') AS product_max_write,
                (SELECT COALESCE(COUNT(*), 0) FROM quotation_quotation WHERE request_quotation_id = %s) AS quotation_count,
                (SELECT COALESCE(MAX(write_date)::text, '') FROM quotation_quotation WHERE request_quotation_id = %s) AS quotation_max_write,
                (SELECT COALESCE(COUNT(*), 0) FROM product_quotation_line WHERE quotation_id IN
                    (SELECT id FROM quotation_quotation WHERE request_quotation_id = %s)) AS line_count,
                (SELECT COALESCE(MAX(write_date)::text, '') FROM product_quotation_line WHERE quotation_id IN
                    (SELECT id FROM quotation_quotation WHERE request_quotation_id = %s)) AS line_max_write
            FROM request_product_quotation_line
            WHERE request_quotation_id = %s
        """, [request_quotation_id, request_quotation_id, request_quotation_id, request_quotation_id, request_quotation_id])

        row = self.env.cr.dictfetchone()
        hash_str = f"{row['product_count']}:{row['product_max_write']}:{row['quotation_count']}:{row['quotation_max_write']}:{row['line_count']}:{row['line_max_write']}"
        return {'hash': hash_str}

    @api.model
    def get_product_wizard_view_id(self):
        """Obtiene la vista form para asignar los productos requeridos,
        se usa en el widget product_board.js"""
        data = self.env['ir.model.data'].sudo().search_read(
            [
                ("module", "=", "purchase_management"),
                ("name", "=", "view_request_quotation_form_add_product"),
            ],
            ["res_id"]
        )
        return data[0]['res_id'] if data else False

    @api.model
    def is_purchase_member(self):
        """Retorna True si el usuario es miembro de Compras o tiene permisos de administrador."""
        if self.env.user.has_group('purchase_management.group_manager_purchase_management'):
            return True
        return self.env['purchase.member'].search_count([
            ('employee_id.user_id', '=', self.env.uid),
        ]) > 0

    @api.model
    def retrieve_sidebar_data(self, my_assigned=False, extra_domain=None):
        """Retorna datos para todas las secciones de la barra lateral.
        Si my_assigned=True, los conteos se filtran por las solicitudes del usuario actual.
        extra_domain: dominio adicional proveniente de los filtros activos del buscador."""
        extra_domain = extra_domain or []
        # Dominio base: combinar filtro de usuario + dominio extra del buscador
        my_domain = []
        if my_assigned:
            uid = self.env.uid
            my_domain = ['|',
                         ('responsible_id.user_id', '=', uid),
                         ('responsible_purchase_id.employee_id.user_id', '=', uid),
                         ]
        base_domain = expression.AND([my_domain, extra_domain])

        # --- ESTADOS ---
        states = ['draft', 'in_shopping', 'sent', 'approved']
        state_counts = {
            state: self.search_count(base_domain + [('state', '=', state)])
            for state in states
        }
        state_counts['pending_approval'] = self.search_count(base_domain + [
            ('state', 'in', [
                'pending_project_approval',
                'pending_purchase_approval',
                'pending_advisory_committee_approval',
            ])
        ])
        state_counts['cancelled'] = self.with_context(active_test=False).search_count(
            base_domain + [('state', '=', 'cancelled')]
        )

        # --- VENCIDAS ---
        _overdue_states = [
            'in_shopping', 'sent',
            'pending_project_approval',
            'pending_purchase_approval',
            'pending_advisory_committee_approval',
        ]
        state_counts['overdue'] = self.search_count(base_domain + [
            ('deadline', '<', fields.Date.today()),
            ('state', 'in', _overdue_states),
        ])

        # --- RESUMEN VENCIDAS ---
        _active_states = _overdue_states
        overdue_records = self.search(base_domain + [
            ('deadline', '<', fields.Date.today()),
            ('state', 'in', _overdue_states),
        ])
        today = fields.Date.today()
        days_list = [
            (today - r.deadline).days for r in overdue_records if r.deadline]
        overdue_summary = {
            # total_active usa solo my_domain (sin extra_domain) para reflejar el total real
            # independientemente del filtro del buscador que el usuario tenga activo
            'total_active': self.search_count(my_domain + [('state', 'in', _active_states)]),
            'by_shopping': sum(1 for r in overdue_records if r.state == 'in_shopping'),
            'by_sent':     sum(1 for r in overdue_records if r.state == 'sent'),
            'by_approval': sum(1 for r in overdue_records if r.state in (
                'pending_project_approval',
                'pending_purchase_approval',
                'pending_advisory_committee_approval',
            )),
            'by_project': sum(1 for r in overdue_records if r.category == 'project'),
            'by_admin':   sum(1 for r in overdue_records if r.category == 'admin'),
            'avg_days': round(sum(days_list) / len(days_list)) if days_list else 0,
            'max_days': max(days_list) if days_list else 0,
        }

        # --- TIPO DE SOLICITUD ---
        # Siempre cargar todos los tipos existentes y contar con base_domain,
        # para que la sección no quede vacía cuando my_assigned está activo.
        all_types = self.env['request.type'].search([])
        types = [
            {
                'id': t.id,
                'name': t.name,
                'count': self.search_count(base_domain + [('type_id', '=', t.id)]),
            }
            for t in all_types
        ]

        # --- CATEGORÍA ---
        categories = {
            'project': self.search_count(base_domain + [('category', '=', 'project')]),
            'admin':   self.search_count(base_domain + [('category', '=', 'admin')]),
        }

        # --- PERSONAL ASIGNADO ---
        # Omitir cuando my_assigned está activo (la sección ya se oculta en frontend)
        if my_assigned:
            return {'states': state_counts, 'types': types, 'categories': categories, 'personnel': [], 'overdue_summary': overdue_summary}

        active_domain = expression.AND(
            [[('state', '!=', 'cancelled')], extra_domain])
        pm_to_emp = {
            pm['id']: (pm['employee_id'][0], pm['employee_id'][1])
            for pm in self.env['purchase.member'].search_read([], ['employee_id'])
            if pm['employee_id']
        }
        all_records = self.search_read(
            active_domain, ['id', 'responsible_id', 'responsible_purchase_id'])
        emp_data = {}
        for rec in all_records:
            involved = set()
            if rec['responsible_id']:
                involved.add((rec['responsible_id'][0],
                             rec['responsible_id'][1]))
            if rec['responsible_purchase_id']:
                emp = pm_to_emp.get(rec['responsible_purchase_id'][0])
                if emp:
                    involved.add(emp)
            for emp_id, emp_name in involved:
                if emp_id not in emp_data:
                    emp_data[emp_id] = {'name': emp_name, 'record_ids': set()}
                emp_data[emp_id]['record_ids'].add(rec['id'])
        personnel = [
            {'id': emp_id, 'name': data['name'],
                'count': len(data['record_ids'])}
            for emp_id, data in emp_data.items()
        ]

        return {'states': state_counts, 'types': types, 'categories': categories, 'personnel': personnel, 'overdue_summary': overdue_summary}

    def _get_product_channel_name(self):
        return f"request_quotation_products{self.id}"

    @api.model
    def subscribe_to_product_updates(self, quotation_id):
        if not quotation_id:
            return False
        quotation = self.browse(quotation_id)
        if not quotation.exists():
            return False

        channel_name = quotation._get_product_channel_name()
        self.env['bus.bus']._sendone(channel_name, 'purchase_management.product/subscribe', {
            'quotation_id': quotation_id,
            'action': 'subscribe',
            'timestamp': fields.Datetime.now().isoformat()
        })
        return channel_name

    def action_toggle_additional_info(self):
        val = self.env['purchase.additional.information'].search(
            [('request_quotation_id', '=', self.id)], limit=1)
        if val:
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.additional.information',
                'view_mode': 'form',
                'target': 'new',
                'res_id': val.id,
            }
        return _show_error_notification(self, _('No existe información adicional para esta solicitud.'))

    def _send_view(self):
        # Sin política de mínimo de proveedores: ir directo al selector de productos.
        if not self.min_providers_qty:
            return {
                'type': 'ir.actions.client',
                'tag': 'purchase_management_product_selector',
                'params': {'request_quotation_id': self.id},
                'name': self.reference,
            }
        # Con política activa: siempre mostrar el wizard con instrucciones,
        # independientemente de si ya se enviaron cotizaciones antes.
        # Esto garantiza que el usuario pueda solicitar una excepción al
        # mínimo de proveedores en cualquier momento del proceso.
        return {
            'default_request_quotation_id': self.id,
            'default_type': 'rfq_to_supplier',
            'default_subject': self.subject,
            'default_show_provider_instructions': True,
            'default_min_providers_qty': self.min_providers_qty,
        }

    def action_rfq_send(self):
        """Enviar correo"""
        if not self.product_line_ids:
            return _show_error_notification(self, _('No existen productos en la solicitud.'))
        self._check_category()
        if self.category == 'project':
            if self.reference == 'Nueva' and self.state == 'draft':
                template = self.env.ref(
                    'purchase_management.mail_template_rfq_to_purchase')
                body = template._render_field('body_html', [self.id])[self.id]
                vals = {
                    'default_request_quotation_id': self.id,
                    'default_type': 'rfq_to_purchase',
                    'default_body': body,
                    'default_subject': self.subject,
                    'default_instructions': True,
                }
            elif self.state in ('in_shopping', 'sent'):
                vals = self._send_view()
            else:
                return _show_error_notification(self, _('Estado no válido para enviar RFQ.'))
        elif self.category == 'admin':
            if self.state == 'draft':
                template = self.env.ref(
                    'purchase_management.mail_template_rfq_to_purchase')
                body = template._render_field('body_html', [self.id])[self.id]
                vals = {
                    'default_request_quotation_id': self.id,
                    'default_type': 'rfq_to_purchase',
                    'default_body': body,
                    'default_subject': self.subject,
                    'default_instructions': True,
                }
            elif self.state in ['in_shopping', 'sent']:
                vals = self._send_view()
            else:
                return _show_error_notification(self, _('Estado no válido para enviar RFQ.'))
        else:
            return _show_error_notification(self, _('Error al enviar el correo. Por favor, comuniquese con el administrador del sistema.'))
        if isinstance(vals, dict) and vals.get('type') == 'ir.actions.client':
            return vals
        return self._open_wizard('purchase.send.mail.wizard', vals)

    def action_send_for_approval(self):
        """Envia correo al lider de proyecto (Aprobacion Tecnica, Observaciones)"""
        if self.state not in ('sent', 'in_shopping'):
            return _show_error_notification(self, _('La solicitud debe estar en "Enviado" o "En Compras".'))
        if len(self.quotation_line_ids) < int(self.min_providers_qty):
            return _show_error_notification(self, _('Se requieren al menos %s cotizaciones.') % self.min_providers_qty)
        if any(url and 'https://importado-desde-excel.com' in url for url in self.quotation_line_ids.mapped('evidence')):
            raise ValidationError(_(
                "Hay cotizaciones importadas que aún no tienen el archivo de evidencia real cargado. "
                "Por favor, actualice la evidencia antes de continuar."
            ))
        template = self.env.ref(
            'purchase_management.mail_template_rfq_to_project_leader')
        body = template._render_field('body_html', [self.id])[self.id]
        return self._open_wizard('purchase.send.mail.wizard', {
            'default_request_quotation_id': self.id,
            'default_type': 'rfq_to_project_manager',
            'default_body': body,
            'default_subject': self.subject,
        })

    def action_approval(self):
        """El sistema adapta la interfaz según el estado de la solicitud: bajo el estado pending_project_approval, la vista permite la aprobación o rechazo de las cotizaciones; mientras que en pending_purchase_approval, las funcionalidades se orientan a la recomendación de las mismas. Tambien manejamos la opcion para aprobar una cantidad de proveedores menor a las politicas corporativas (3 actualmente) al momento de crear las cotizaciones."""
        approval_mode = 'recommend' if (self.state == 'pending_purchase_approval' and self.category == 'project') or (
            self.category == 'admin' and self.state == 'sent') else 'approve'
        if self.state not in ['pending_project_approval', 'pending_purchase_approval'] and not self.is_min_providers_approval_pending and self.category == 'project':
            return _show_error_notification(self, _('Estado no válido. Por favor, comuniquese con el administrador del sistema.'))
        if not self.quotation_line_ids and not self.is_min_providers_approval_pending:
            return _show_error_notification(self, _('No existen cotizaciones para %s. Por favor, verifique e intente nuevamente.') % ('aprobar' if approval_mode == 'approve' else 'recomendar'))
        if len(self.quotation_line_ids) < int(self.min_providers_qty) and not self.is_min_providers_approval_pending:
            return _show_error_notification(self, _('Se requieren al menos %s cotizaciones. Por favor, verifique e intente nuevamente.') % self.min_providers_qty)
        if not (self.is_min_providers_approval_pending or self.rejected_by_project_leader):
            return self._open_wizard('approval.observation.wizard', {
                'default_request_quotation_id': self.id,
                'default_approval_mode': approval_mode,
            })
        elif self.rejected_by_project_leader:
            return self._open_wizard('approval.observation.wizard', {
                'default_request_quotation_id': self.id,
                'default_rejected_by_project_leader': True,
            })
        else:
            msg = Markup(
                f"<span>Se aprueba trabajar con <span style='color: #017e84;'>{self.min_providers_qty} {'proveedor' if self.min_providers_qty == 1 else 'proveedores'}</span> en lugar del mínimo de <span style='color: #017e84;'>{self.env['ir.config_parameter'].sudo().get_param('purchase_management.min_providers_qty', default=3)}</span> establecido por política. El lider de proyecto puede proceder a crear las cotizaciones según este número de proveedores aprobado.</span>")
            self.sudo().message_post(body=msg)
            self.sudo().write({'is_min_providers_approval_pending': False})

    def action_pause_request(self):
        """Pausa la solicitud"""
        self.ensure_one()
        self.pause_request = True

    def action_resume_request(self):
        """Reanuda la solicitud"""
        self.ensure_one()
        self.pause_request = False

    def action_present_comparative_chart(self):
        """Despliega el cuadro comparativo"""
        return {
            'type': 'ir.actions.client',
            'tag': 'purchase_management_comparative_chart',
            'params': {'request_quotation_id': self.id}
        }

    def action_reject_request(self):
        """Rechaza la solicitud (Aprobacion minima de proveedores o lider de proyecto)"""
        if not self.is_min_providers_approval_pending and not self.rejected_by_project_leader:
            return _show_error_notification(self, _('Estado no válido para rechazar.'))
        return self._open_wizard('reject.request.wizard', {
            'default_request_quotation_id': self.id,
            'default_view': 'min_providers_qty' if not self.rejected_by_project_leader else 'project_leader',
        })

    def action_view_traceability(self):
        if len(self.purchase_order_ids) == 1:
            return {
                'name': _('Orden de compra'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.management.order',
                'view_mode': 'form',
                'res_id': self.purchase_order_ids.id,
                'target': 'current',
            }
        else:
            return {
                'name': _('Ordenes de compra'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.management.order',
                'view_mode': 'list,form',
                'domain': [('request_quotation_id', '=', self.id)],
                'target': 'current',
            }

    def action_return_to_requester(self):
        """Devuelve la SDC al solicitante con un motivo"""
        if self.state not in ('in_shopping', 'sent'):
            return _show_error_notification(self, _('Solo se puede devolver la solicitud cuando está en estado "En Compras" o "Enviada".'))
        return self._open_wizard('return.to.requester.wizard', {
            'default_request_quotation_id': self.id,
        })

    def action_resubmit_after_return(self):
        """Reenvía la SDC a Compras después de correcciones (desde estado devuelta)"""
        if self.state != 'returned':
            return _show_error_notification(self, _('Estado no válido para reenviar la solicitud.'))
        if not self.responsible_purchase_id:
            return _show_error_notification(self, _('No hay responsable de Compras asignado. Comuníquese con el administrador.'))
        template = self.env.ref('purchase_management.mail_template_rfq_to_purchase')
        template.send_mail(
            self.id,
            email_values={
                'email_to': self.responsible_purchase_id.employee_id.work_email,
                'email_cc': self.responsible_id.work_email,
                'subject': self.subject + f" - {self.reference}",
            }
        )
        self.sudo().write({'state': 'in_shopping'})
        msg = Markup(
            f"<span>La solicitud fue reenviada al área de "
            f"<span style='color: #017e84;'>Compras</span> "
            f"(<span style='color: #017e84;'>{self.responsible_purchase_id.employee_id.name}</span>) "
            f"tras las correcciones realizadas.</span>"
        )
        self.sudo().message_post(body=msg)

    def action_cancel(self):
        """Cancela la solicitud"""
        if self.state in ('cancelled', 'done'):
            return _show_error_notification(self, _('Ya está cancelado o hecho.'))
        return self._open_wizard('cancel.request.quotation.wizard', {
            'default_request_quotation_id': self.id,
        })

    def _open_wizard(self, res_model, context):
        return {
            'name': 'Odoo',
            'type': 'ir.actions.act_window',
            'res_model': res_model,
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    # ── Creación de órdenes de compra desde el wizard de vinculación ──────────

    def action_create_purchase_orders(self, mappings, distributions, delivery_data=None):
        """Crea las órdenes de compra a partir del wizard de vinculación de productos.

        Operación atómica que ejecuta los siguientes pasos en orden:
          1. Valida que la solicitud esté en estado 'approved'.
          2. Valida las distribuciones de cantidad por proveedor.
          3. Crea o recupera (con deduplicación) las variantes pendientes.
          4. Guarda warehouse_variant_id y cost_center_id en cada línea.
          5. Crea una purchase.management.order por proveedor adjudicado.
          6. Cambia el estado de la solicitud a 'order_created'.

        Args:
            mappings (list[dict]): Un dict por línea de solicitud con:
                - line_id (int): ID de request.product.quotation.line
                - variant_id (int | None): variante ya existente en BD
                - pending_creation (dict | None): datos para crear variante nueva
                    {mode, variant_name, estimated_price,
                     product_name, category_id, type_product_id, description,  # modo 'product'
                     product_id}                                                 # modo 'variant'
                - cost_center_id (int | None)
            distributions (list[dict]): Un dict por línea de cotización con:
                - qline_id (int): ID de product.quotation.line
                - line_id (int): ID de request.product.quotation.line
                - assigned_qty (float): cantidad asignada a ese proveedor

        Returns:
            list[dict]: Variantes creadas/encontradas, con:
                {line_id, variant_id, variant_name, product_name, already_existed}

        Raises:
            UserError: Si hay errores de validación, datos faltantes o fallas al crear registros.
        """
        self.ensure_one()
        self._check_quotation_state_for_order()
        self._validate_distributions(distributions)
        created_variants = self._resolve_pending_variants(mappings)
        self._save_line_mappings(mappings)
        self._create_orders_from_distributions(
            distributions, delivery_data=delivery_data or {})
        self.write({'state': 'order_created'})
        return created_variants

    def _check_quotation_state_for_order(self):
        """Valida que la solicitud esté en estado 'approved' antes de crear la OC."""
        if self.state == 'order_created':
            raise UserError(
                _('Esta solicitud ya fue confirmada. No se puede modificar.'))
        if self.state != 'approved':
            raise UserError(_(
                'La solicitud debe estar en estado "Aprobado" para confirmar '
                '(estado actual: %s).'
            ) % self.state)

    def _validate_distributions(self, distributions):
        """Valida que ninguna cantidad asignada sea negativa y que la suma
        por línea de solicitud no supere la cantidad pedida.

        Raises:
            UserError: Si alguna cantidad es negativa o supera lo solicitado.
        """
        Line = self.env['request.product.quotation.line'].sudo()
        QLine = self.env['product.quotation.line'].sudo()

        for dist in distributions:
            if float(dist.get('assigned_qty') or 0) < 0:
                raise UserError(_(
                    'La cantidad asignada no puede ser negativa (qline_id=%s).'
                ) % dist.get('qline_id'))

        # Acumular totales asignados por línea de solicitud
        dist_by_request_line = {}
        for dist in distributions:
            qline_id = int(dist.get('qline_id') or 0)
            if not qline_id:
                continue
            qline = QLine.browse(qline_id)
            if not qline.exists():
                raise UserError(
                    _('Línea de cotización no encontrada (qline_id=%s).') % qline_id)
            req_line_id = qline.request_line_id.id if qline.request_line_id else None
            if req_line_id:
                dist_by_request_line.setdefault(req_line_id, 0)
                dist_by_request_line[req_line_id] += float(
                    dist.get('assigned_qty') or 0)

        for req_line_id, total_assigned in dist_by_request_line.items():
            req_line = Line.browse(req_line_id)
            if req_line.exists() and total_assigned > req_line.qty:
                raise UserError(_(
                    'La distribución para "%s" (%s) supera la cantidad solicitada (%s).'
                ) % (req_line.name or req_line_id, int(total_assigned), int(req_line.qty)))

    def _resolve_pending_variants(self, mappings):
        """Crea o recupera (con deduplicación) los warehouse.product y
        warehouse.product.variant marcados como pending_creation en cada mapping.

        Soporta tres modos:
          - 'product'           → crea producto nuevo + primera variante
          - 'variant'           → agrega variante a producto ya existente en BD
          - 'variant_of_pending'→ agrega variante a un producto que otra línea
                                  del mismo lote está creando en modo 'product'

        Proceso en dos pasos:
          Paso 1: crear/recuperar todos los productos (modo 'product') y poblar
                  product_cache antes de procesar cualquier 'variant_of_pending'.
          Paso 2: crear todas las variantes usando el cache ya completo.

        Actualiza mapping['variant_id'] in-place para que los pasos siguientes
        puedan usar el ID resuelto sin importar si la variante es nueva o existente.

        Returns:
            list[dict]: Resumen de variantes procesadas.

        Raises:
            UserError: Si faltan datos obligatorios o falla la creación de registros.
        """
        WProduct = self.env['warehouse.product'].sudo()
        WVariant = self.env['warehouse.product.variant'].sudo()
        currency = self.env['res.currency'].sudo().search(
            [('name', '=', 'COP')], limit=1)
        if not currency:
            currency = self.env.company.currency_id

        # normalized_name -> warehouse.product (evita crear duplicados en un mismo lote)
        product_cache = {}
        created_variants = []

        # ── Paso 1: crear/recuperar todos los productos de modo 'product' ─────
        # Garantiza que product_cache esté completo antes de resolver
        # 'variant_of_pending', independientemente del orden de los mappings.
        for mapping in mappings:
            pending = mapping.get('pending_creation')
            if not pending or pending.get('mode') != 'product':
                continue

            product_name_raw = (pending.get('product_name') or '').strip()
            category_id = pending.get('category_id')
            type_product_id = pending.get('type_product_id')
            description = (pending.get('description') or '').strip()

            if not all([product_name_raw, category_id, type_product_id, description]):
                raise UserError(_(
                    'Faltan campos para crear el producto (línea %s).'
                ) % mapping.get('line_id'))

            normalized_name = self._normalize_wh_name(product_name_raw)
            if normalized_name not in product_cache:
                existing_product = WProduct.search(
                    [('name', '=', normalized_name)], limit=1)
                if existing_product:
                    product_cache[normalized_name] = existing_product
                else:
                    product_cache[normalized_name] = WProduct.create({
                        'name': product_name_raw,
                        'category_id': int(category_id),
                        'type_product_id': int(type_product_id),
                        'description': description,
                    })

        # ── Paso 2: crear variantes para todos los pending ────────────────────
        for mapping in mappings:
            pending = mapping.get('pending_creation')
            if not pending:
                continue

            mode = pending.get('mode', 'product')
            variant_name_raw = (pending.get('variant_name') or '').strip()
            estimated_price = float(pending.get('estimated_price') or 0)

            if not variant_name_raw:
                raise UserError(_(
                    'El nombre de la variante es obligatorio (línea %s).'
                ) % mapping.get('line_id'))
            if estimated_price < 0:
                raise UserError(_(
                    'El precio estimado no puede ser negativo (línea %s).'
                ) % mapping.get('line_id'))

            if mode == 'product':
                # El producto ya fue creado en el Paso 1 — solo recuperar del cache
                product_name_raw = (pending.get('product_name') or '').strip()
                normalized_name = self._normalize_wh_name(product_name_raw)
                product = product_cache[normalized_name]

            elif mode == 'variant_of_pending':
                # Variante de un producto pendiente creado en otra línea del mismo lote
                pending_product_name = (pending.get(
                    'pending_product_name') or '').strip()
                if not pending_product_name:
                    raise UserError(_(
                        'Falta el nombre del producto pendiente (línea %s).'
                    ) % mapping.get('line_id'))
                normalized_name = self._normalize_wh_name(pending_product_name)
                if normalized_name not in product_cache:
                    # Red de seguridad: buscar en BD por si el producto ya existía
                    existing_product = WProduct.search(
                        [('name', '=', normalized_name)], limit=1)
                    if existing_product:
                        product_cache[normalized_name] = existing_product
                    else:
                        raise UserError(_(
                            'El producto pendiente "%s" no fue encontrado. '
                            'Verifica que otra línea lo esté creando como producto nuevo.'
                        ) % pending_product_name)
                product = product_cache[normalized_name]

            else:  # mode == 'variant' — variante sobre producto ya existente en BD
                product_id = pending.get('product_id')
                if not product_id:
                    raise UserError(_(
                        'Debe seleccionar un producto existente (línea %s).'
                    ) % mapping.get('line_id'))
                product = WProduct.browse(int(product_id))
                if not product.exists():
                    raise UserError(_(
                        'El producto seleccionado no existe (línea %s).'
                    ) % mapping.get('line_id'))

            # Deduplicación: el nombre se normaliza igual que en warehouse.product.variant.create()
            normalized_variant = unicodedata.normalize('NFD', variant_name_raw).encode(
                'ascii', 'ignore').decode('ascii').title()
            existing_variant = WVariant.search([
                ('product_id', '=', product.id),
                ('name', '=', normalized_variant),
            ], limit=1)

            if existing_variant:
                mapping['variant_id'] = existing_variant.id
                created_variants.append({
                    'line_id': mapping.get('line_id'),
                    'variant_id': existing_variant.id,
                    'variant_name': existing_variant.name,
                    'product_name': product.name,
                    'already_existed': True,
                })
            else:
                new_variant = WVariant.create({
                    'product_id': product.id,
                    'name': variant_name_raw,
                    'estimated_price': estimated_price,
                    'currency_id': currency.id,
                })
                mapping['variant_id'] = new_variant.id
                created_variants.append({
                    'line_id': mapping.get('line_id'),
                    'variant_id': new_variant.id,
                    'variant_name': new_variant.name,
                    'product_name': product.name,
                    'already_existed': False,
                })

        return created_variants

    def _save_line_mappings(self, mappings):
        """Escribe warehouse_variant_id y cost_center_id en cada
        request.product.quotation.line según el mapeo resuelto.
        También guarda automáticamente el nombre de la línea como alias de la
        variante si difiere del nombre oficial (aprendizaje automático).

        Raises:
            UserError: Si alguna línea no existe, pertenece a otra solicitud
                       o no tiene variante resuelta.
        """
        Line = self.env['request.product.quotation.line'].sudo()
        Alias = self.env['warehouse.variant.alias'].sudo()

        for mapping in mappings:
            line_id = int(mapping.get('line_id') or 0)
            if not line_id:
                continue
            line = Line.browse(line_id)
            if not line.exists() or line.request_quotation_id.id != self.id:
                raise UserError(_(
                    'Línea de solicitud inválida (line_id=%s).'
                ) % line_id)
            variant_id = mapping.get('variant_id')
            if not variant_id:
                raise UserError(_(
                    'No se pudo resolver la variante para la línea %s.'
                ) % line_id)
            line.write({
                'warehouse_variant_id': int(variant_id),
                'cost_center_id': mapping.get('cost_center_id') or False,
            })

            # ── Auto-aprendizaje de alias ──────────────────────────────────
            # Si el nombre con el que el usuario pidió el producto difiere del
            # nombre oficial de la variante, lo guardamos como alias para que
            # el sistema lo reconozca automáticamente la próxima vez.
            if line.name:
                line_norm = unicodedata.normalize('NFD', line.name).encode(
                    'ascii', 'ignore').decode('ascii').title()
                variant = self.env['warehouse.product.variant'].browse(
                    int(variant_id))
                if variant.exists() and line_norm != variant.name:
                    existing = Alias.search([
                        ('name', '=', line_norm),
                        ('variant_id', '=', variant.id),
                    ], limit=1)
                    if not existing:
                        Alias.create(
                            {'name': line_norm, 'variant_id': variant.id})

    def _create_orders_from_distributions(self, distributions, delivery_data=None):
        """Persiste assigned_qty en cada product.quotation.line y crea una
        purchase.management.order (con sus líneas) por cada proveedor adjudicado.

        Solo se incluyen en la OC las líneas con assigned_qty > 0.

        Raises:
            UserError: Si alguna línea de solicitud no tiene variante o centro de costo,
                       o si los registros referenciados no existen.
        """
        Line = self.env['request.product.quotation.line'].sudo()
        QLine = self.env['product.quotation.line'].sudo()
        Order = self.env['purchase.management.order'].sudo()
        OrderLine = self.env['purchase.management.order.line'].sudo()

        dd = delivery_data or {}

        # Primer paso: agrupar ítems por quotation (= proveedor adjudicado)
        # quotation.id -> {'quotation': obj, 'items': [(req_line, qline, qty)]}
        orders_map = {}

        for dist in distributions:
            qline_id = int(dist.get('qline_id') or 0)
            req_line_id = int(dist.get('line_id') or 0)
            assigned_qty = float(dist.get('assigned_qty') or 0)

            if not qline_id:
                continue

            qline = QLine.browse(qline_id)
            if not qline.exists():
                raise UserError(
                    _('Línea de cotización no encontrada (qline_id=%s).') % qline_id)
            if not qline.quotation_id.exists():
                raise UserError(_(
                    'La cotización de la línea qline_id=%s no existe.'
                ) % qline_id)

            # Persistir cantidad asignada siempre (incluso si es 0)
            qline.write({'assigned_qty': assigned_qty})

            if assigned_qty <= 0:
                continue

            # Resolver la línea de solicitud: primero desde line_id del payload,
            # con fallback a request_line_id del qline
            if req_line_id:
                req_line = Line.browse(req_line_id)
                if not req_line.exists():
                    raise UserError(_(
                        'Línea de solicitud no encontrada (line_id=%s).'
                    ) % req_line_id)
            elif qline.request_line_id:
                req_line = qline.request_line_id
            else:
                raise UserError(_(
                    'No se pudo determinar la línea de solicitud para qline_id=%s. '
                    'Actualice el wizard y vuelva a intentarlo.'
                ) % qline_id)

            quotation = qline.quotation_id
            if quotation.id not in orders_map:
                orders_map[quotation.id] = {
                    'quotation': quotation, 'items': []}
            orders_map[quotation.id]['items'].append(
                (req_line, qline, assigned_qty))

        # Segundo paso: crear una OC por proveedor con sus líneas
        for _qid, data in orders_map.items():
            quotation = data['quotation']

            for req_line, _qline, _qty in data['items']:
                if not req_line.warehouse_variant_id:
                    raise UserError(_(
                        'La línea "%s" no tiene variante de bodega asignada. '
                        'Verifique el mapeo.'
                    ) % (req_line.name or req_line.id))
                if not req_line.cost_center_id:
                    raise UserError(_(
                        'La línea "%s" no tiene centro de costo. '
                        'Asigne un centro de costo a todas las líneas antes de confirmar.'
                    ) % (req_line.name or req_line.id))

            # Resolver el partner para la OC: busca en res.partner por supplier_name
            partner = self.env['res.partner'].sudo().search([
                ('name', '=ilike', (quotation.supplier_name or '').strip()),
                ('is_supplier', '=', True),
            ], limit=1)
            if not partner:
                raise UserError(
                    _('El proveedor "%s" no tiene un contacto registrado en el sistema. '
                      'Confirme el wizard nuevamente para crearlo.')
                    % quotation.supplier_name
                )

            order_vals = {
                'request_quotation_id': self.id,
                'type_id': self.type_id.id,
                'partner_id': partner.id,
                'currency_id': quotation.currency_id.id,
                'trm': quotation.trm,
                'trm_date': quotation.trm_date,
                'payment_term': quotation.payment_term or '',
                'delivery_date': quotation.delivery_date,
                'project_id': self.project_id.id,
                'reference': self.env['ir.sequence'].next_by_code('purchase.management.order') or '/',
                'subject': self.subject,
                'reason': self.reason,
            }
            if dd.get('name', '').strip():
                order_vals['delivery_contact_name'] = dd['name'].strip()
            if dd.get('email', '').strip():
                order_vals['delivery_email'] = dd['email'].strip()
            if dd.get('phone', '').strip():
                order_vals['delivery_phone'] = dd['phone'].strip()
            if dd.get('address', '').strip():
                order_vals['delivery_address'] = dd['address'].strip()
            order = Order.create(order_vals)

            for req_line, qline, qty in data['items']:
                OrderLine.create({
                    'order_id': order.id,
                    'product_id': req_line.warehouse_variant_id.id,
                    'cost_center_id': req_line.cost_center_id.id,
                    'qty': qty,
                    'price_unit': qline.price_unit,
                    'currency_id': quotation.currency_id.id,
                })

    @staticmethod
    def _normalize_wh_name(name):
        """Replica la normalización de warehouse.product: quita acentos (NFD→ASCII)
        y capitaliza la primera letra. Usado para deduplicar nombres de productos."""
        cleaned = unicodedata.normalize('NFD', name or '').encode(
            'ascii', 'ignore').decode('ascii')
        return cleaned.capitalize()

    @api.model
    def get_dashboard_data(self, member_id=False):
        import calendar as _cal
        from dateutil.relativedelta import relativedelta
        today = fields.Date.context_today(self)

        SDC = self.env['request.quotation']
        OC = self.env['purchase.management.order']

        # Excluir borradores de todos los conteos del dashboard
        sdc_domain = [('state', '!=', 'draft')]
        if member_id:
            sdc_domain.append(('responsible_purchase_id', '=', member_id))

        _pending_states = ['pending_project_approval',
                           'pending_purchase_approval', 'pending_advisory_committee_approval']
        _overdue_eligible = ['in_shopping', 'sent'] + _pending_states

        sdc_total = SDC.search_count(sdc_domain)
        sdc_in_process = SDC.search_count(
            sdc_domain + [('state', 'in', ['in_shopping', 'sent'])])
        sdc_pending = SDC.search_count(
            sdc_domain + [('state', 'in', _pending_states)])
        sdc_overdue = SDC.search_count(sdc_domain + [
            ('deadline', '<', today),
            ('state', 'in', _overdue_eligible),
        ])
        sdc_order_created = SDC.search_count(
            sdc_domain + [('state', '=', 'order_created')])

        oc_domain = []
        if member_id:
            oc_domain.append(
                ('request_quotation_id.responsible_purchase_id', '=', member_id))

        oc_total = OC.search_count(oc_domain)
        oc_sent = OC.search_count(oc_domain + [('state', '=', 'sent')])
        oc_caused = OC.search_count(oc_domain + [('state', '=', 'caused')])
        oc_paid = OC.search_count(oc_domain + [('state', '=', 'paid')])

        # TRM — tasa representativa del mercado (COP por unidad de divisa)
        currencies = {}
        for curr_name in ['USD', 'EUR']:
            curr = self.env['res.currency'].search(
                [('name', '=', curr_name), ('active', '=', True)], limit=1)
            if curr:
                try:
                    trm = round(1.0 / curr.rate, 2) if curr.rate else 0
                    currencies[curr_name] = {
                        'rate': trm, 'symbol': curr.symbol or curr_name}
                except Exception:
                    pass

        # Fechas límite del mes actual para el calendario
        month_start = today.replace(day=1)
        last_day = _cal.monthrange(today.year, today.month)[1]
        month_end = today.replace(day=last_day)
        deadline_recs = SDC.search(sdc_domain + [
            ('deadline', '>=', month_start),
            ('deadline', '<=', month_end),
            ('state', 'not in', ['cancelled', 'order_created']),
        ])
        deadlines = list(set(str(r.deadline)
                         for r in deadline_recs if r.deadline))

        SDC_LABELS = {
            'draft': 'Borrador',
            'in_shopping': 'En Compras',
            'sent': 'Enviado',
            'pending_project_approval': 'Pend. Líder Proy.',
            'pending_purchase_approval': 'Pend. Compras',
            'pending_advisory_committee_approval': 'Pend. Comité',
            'approved': 'Aprobado',
            'order_created': 'Orden Creada',
            'cancelled': 'Cancelado',
        }
        OC_LABELS = {'draft': 'Borrador', 'sent': 'Enviado',
                     'caused': 'Causado', 'paid': 'Pagado'}

        recent_sdc = [{
            'id': r.id,
            'reference': r.reference or '',
            'subject': (r.subject or '')[:45],
            'state': r.state,
            'state_label': SDC_LABELS.get(r.state, r.state),
            'deadline': r.deadline.strftime('%d/%m/%Y') if r.deadline else '',
            'project': r.project_id.name if r.project_id else '',
            'days_left': (r.deadline - today).days if r.deadline else None,
            'urgency': (
                'overdue' if r.deadline and r.deadline < today else
                'critical' if r.deadline and (r.deadline - today).days <= 2 else
                'urgent' if r.deadline and (r.deadline - today).days <= 5 else
                'ok'
            ),
        } for r in SDC.search(sdc_domain, order='create_date desc', limit=20)]

        recent_oc = [{
            'id': r.id,
            'reference': r.reference or '',
            'subject': (r.subject or '')[:45],
            'state': r.state,
            'state_label': OC_LABELS.get(r.state, r.state),
            'partner': r.partner_id.name if r.partner_id else '',
            'total': r.total or 0,
            'currency_symbol': r.currency_id.symbol if r.currency_id else '$',
            'payment_term': r.payment_term or '',
        } for r in OC.search(oc_domain, order='create_date desc', limit=8)]

        month_start = today.replace(day=1)
        prev_month_start = month_start - relativedelta(months=1)

        sdc_this_month = SDC.search_count(
            sdc_domain + [('create_date', '>=', month_start)])
        sdc_prev_month = SDC.search_count(sdc_domain + [
            ('create_date', '>=', prev_month_start),
            ('create_date', '<', month_start),
        ])

        sdc_monthly = []
        for i in range(5, -1, -1):
            m_start = month_start - relativedelta(months=i)
            m_end = m_start + relativedelta(months=1)
            cnt = SDC.search_count(sdc_domain + [
                ('create_date', '>=', m_start),
                ('create_date', '<', m_end),
            ])
            sdc_monthly.append(
                {'month': m_start.strftime('%b %Y'), 'count': cnt})

        _active_sdc_states = [
            'draft', 'in_shopping', 'sent',
            'pending_project_approval', 'pending_purchase_approval',
            'pending_advisory_committee_approval', 'approved', 'order_created',
        ]
        sdc_by_state = {
            st: SDC.search_count(sdc_domain + [('state', '=', st)])
            for st in _active_sdc_states
        }

        oc_monthly = []
        for i in range(5, -1, -1):
            m_start = month_start - relativedelta(months=i)
            m_end = m_start + relativedelta(months=1)
            ocs = OC.search(oc_domain + [
                ('create_date', '>=', m_start),
                ('create_date', '<', m_end),
            ])
            oc_monthly.append({
                'month': m_start.strftime('%b %Y'),
                'count': len(ocs),
                'total': sum(ocs.mapped('total')),
            })

        oc_total_value = sum(OC.search(oc_domain).mapped('total'))

        # Mapa de vencimientos SDC por fecha (para el calendario)
        deadline_records = SDC.search(sdc_domain + [
            ('deadline', '!=', False),
            ('state', 'in', _overdue_eligible),
        ])
        sdc_deadline_map = {}
        for r in deadline_records:
            date_str = r.deadline.strftime('%Y-%m-%d')
            days_diff = (r.deadline - today).days
            urgency = (
                'overdue' if days_diff < 0 else
                'critical' if days_diff <= 2 else
                'urgent' if days_diff <= 7 else
                'ok'
            )
            if date_str not in sdc_deadline_map:
                sdc_deadline_map[date_str] = []
            sdc_deadline_map[date_str].append({
                'id': r.id,
                'reference': r.reference or '',
                'subject': (r.subject or '')[:35],
                'urgency': urgency,
                'days_left': days_diff,
            })

        # SDC sin responsable de compras asignado (en estados que lo requieren)
        sdc_unassigned = SDC.search_count(sdc_domain + [
            ('responsible_purchase_id', '=', False),
            ('state', 'in', ['in_shopping', 'pending_purchase_approval']),
        ])

        # Valor OC mes anterior (para comparativa mensual)
        oc_prev_month_recs = OC.search(oc_domain + [
            ('create_date', '>=', prev_month_start),
            ('create_date', '<', month_start),
        ])
        oc_prev_month_value = sum(oc_prev_month_recs.mapped('total'))

        # SDC por categoría (Proyecto vs Administrativo)
        sdc_category_project = SDC.search_count(
            sdc_domain + [('category', '=', 'project')])
        sdc_category_admin = SDC.search_count(
            sdc_domain + [('category', '=', 'admin')])

        # OC en divisas extranjeras con estimado COP
        oc_foreign_recs = OC.search(
            oc_domain + [('currency_id.name', '!=', 'COP')])
        oc_foreign_count = len(oc_foreign_recs)
        oc_foreign_value_cop = sum((r.total or 0) * (r.trm or 1)
                                   for r in oc_foreign_recs)

        # SDC por gestión (Administrativas globales + Proyectos del integrante)
        # Solo solicitudes pendientes de aprobación del COMITÉ
        _committee_state = 'pending_advisory_committee_approval'

        # 1. Administrativas en Comité (siempre globales)
        sdc_admin_committee = SDC.search_count([
            ('category', '=', 'admin'),
            ('state', '=', _committee_state)
        ])

        # 2. Proyectos en Comité (filtrados por integrante si member_id está presente)
        proj_committee_domain = [
            ('category', '=', 'project'), ('state', '=', _committee_state)]
        if member_id:
            proj_committee_domain.append(
                ('responsible_purchase_id', '=', member_id))
        sdc_proj_committee = SDC.search_count(proj_committee_domain)

        sdc_management_total = sdc_admin_committee + sdc_proj_committee

        # Aprobadas listas para OC: admin siempre global + proyectos filtrados por integrante
        approved_admin = SDC.search_count(
            [('state', '=', 'approved'), ('category', '=', 'admin')])
        approved_proj_domain = [
            ('state', '=', 'approved'), ('category', '=', 'project')]
        if member_id:
            approved_proj_domain.append(
                ('responsible_purchase_id', '=', member_id))
        approved_proj = SDC.search_count(approved_proj_domain)
        sdc_approved_count = approved_admin + approved_proj

        return {
            'today': str(today),
            'sdc': {
                'total': sdc_total,
                'in_process': sdc_in_process,
                'pending': sdc_pending,
                'overdue': sdc_overdue,
                'order_created': sdc_order_created,
                'management_total': sdc_management_total,
            },
            'oc': {
                'total': oc_total,
                'sent': oc_sent,
                'caused': oc_caused,
                'paid': oc_paid,
            },
            'currencies': currencies,
            'deadlines': deadlines,
            'recent_sdc': recent_sdc,
            'recent_oc': recent_oc,
            'sdc_this_month': sdc_this_month,
            'sdc_prev_month': sdc_prev_month,
            'sdc_monthly': sdc_monthly,
            'sdc_by_state': sdc_by_state,
            'oc_monthly': oc_monthly,
            'oc_total_value': oc_total_value,
            'sdc_deadline_map': sdc_deadline_map,
            'sdc_unassigned': sdc_unassigned,
            'oc_prev_month_value': oc_prev_month_value,
            'sdc_category_project': sdc_category_project,
            'sdc_category_admin': sdc_category_admin,
            'oc_foreign_count': oc_foreign_count,
            'oc_foreign_value_cop': oc_foreign_value_cop,
            'sdc_approved_count': sdc_approved_count,
        }

    @api.model
    def get_dashboard_trends(self, sdc_months=6, oc_months=6, member_id=False):
        from dateutil.relativedelta import relativedelta
        today = fields.Date.today()
        month_start = today.replace(day=1)

        SDC = self.env['request.quotation']
        OC = self.env['purchase.management.order']

        sdc_domain = []
        if member_id:
            sdc_domain.append(('responsible_purchase_id', '=', member_id))
        oc_domain = []
        if member_id:
            oc_domain.append(
                ('request_quotation_id.responsible_purchase_id', '=', member_id))

        def _build_months(n_months):
            if n_months == 0:
                year_start = today.replace(month=1, day=1)
                months_count = today.month
                return [(year_start + relativedelta(months=i), year_start + relativedelta(months=i + 1)) for i in range(months_count)]
            if n_months == -1:
                n_months = 24
            return [(month_start - relativedelta(months=i), month_start - relativedelta(months=i - 1)) for i in range(n_months - 1, -1, -1)]

        sdc_monthly = []
        for m_start, m_end in _build_months(sdc_months):
            cnt = SDC.search_count(sdc_domain + [
                ('create_date', '>=', m_start),
                ('create_date', '<', m_end),
            ])
            sdc_monthly.append(
                {'month': m_start.strftime('%b %Y'), 'count': cnt})

        oc_monthly = []
        for m_start, m_end in _build_months(oc_months):
            ocs = OC.search(oc_domain + [
                ('create_date', '>=', m_start),
                ('create_date', '<', m_end),
            ])
            oc_monthly.append({
                'month': m_start.strftime('%b %Y'),
                'count': len(ocs),
                'total': sum(ocs.mapped('total')),
            })

        return {'sdc_monthly': sdc_monthly, 'oc_monthly': oc_monthly}

    @api.model
    def get_dashboard_charts_data(self, member_id=False):
        from dateutil.relativedelta import relativedelta
        today = fields.Date.context_today(self)

        SDC = self.env['request.quotation']
        OC = self.env['purchase.management.order']

        sdc_domain = [('state', '!=', 'draft')]
        if member_id:
            sdc_domain.append(('responsible_purchase_id', '=', member_id))
        oc_domain = []
        if member_id:
            oc_domain.append(
                ('request_quotation_id.responsible_purchase_id', '=', member_id))

        # --- TENDENCIA MENSUAL (últimos 6 meses) ---
        _MONTHS_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May',
                      'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        month_cur = today.replace(day=1)
        monthly_trend = []
        for i in range(5, -1, -1):
            m_start = month_cur - relativedelta(months=i)
            m_end = m_start + relativedelta(months=1) - timedelta(days=1)
            cnt = SDC.search_count(sdc_domain + [
                ('create_date', '>=', m_start),
                ('create_date', '<', m_start + relativedelta(months=1)),
            ])
            monthly_trend.append({
                'label': f"{_MONTHS_ES[m_start.month - 1]} {m_start.year}",
                'month_start': str(m_start),
                'month_end': str(m_end),
                'count': cnt,
            })

        # --- TOP PROYECTOS (enriquecidos con estado dominante y alerta de vencimiento) ---
        _overdue_eligible_ch = [
            'in_shopping', 'sent', 'pending_project_approval',
            'pending_purchase_approval', 'pending_advisory_committee_approval',
        ]
        _SDC_LABELS_CH = {
            'draft': 'Borrador', 'in_shopping': 'En Compras', 'sent': 'Enviado',
            'pending_project_approval': 'Pend. Proy.', 'pending_purchase_approval': 'Pend. Compras',
            'pending_advisory_committee_approval': 'Pend. Comité',
            'approved': 'Aprobado', 'order_created': 'Orden Creada', 'cancelled': 'Cancelado',
        }
        sdc_proj = SDC.search(sdc_domain + [('project_id', '!=', False)])
        proj_data = sdc_proj.read(['project_id', 'state'])
        proj_counts = {}
        for r in proj_data:
            pid, pname = r['project_id']
            if pid not in proj_counts:
                proj_counts[pid] = {'id': pid, 'name': pname,
                                    'count': 0, 'state_counts': {}}
            proj_counts[pid]['count'] += 1
            st = r['state']
            proj_counts[pid]['state_counts'][st] = proj_counts[pid]['state_counts'].get(
                st, 0) + 1
        top_projects_raw = sorted(proj_counts.values(
        ), key=lambda x: x['count'], reverse=True)[:5]
        top_projects_enriched = []
        for proj in top_projects_raw:
            sc = proj['state_counts']
            dominant = max(sc, key=sc.get) if sc else 'draft'
            has_overdue = SDC.search_count(sdc_domain + [
                ('project_id', '=', proj['id']),
                ('deadline', '<', today),
                ('state', 'in', _overdue_eligible_ch),
            ]) > 0
            top_projects_enriched.append({
                'id': proj['id'], 'name': proj['name'], 'count': proj['count'],
                'dominant_state': dominant,
                'dominant_state_label': _SDC_LABELS_CH.get(dominant, dominant),
                'has_overdue': has_overdue,
            })

        # --- TOP PROVEEDORES (por valor acumulado en OC + calificación del proveedor) ---
        ocs_all = OC.search(oc_domain + [('partner_id', '!=', False)])
        sup_by_value = {}
        for oc in ocs_all:
            pid = oc.partner_id.id
            if pid not in sup_by_value:
                sup_by_value[pid] = {
                    'id': pid, 'name': oc.partner_id.name,
                    'count': 0, 'value': 0.0,
                    'qualification': oc.partner_id.qualification or '0',
                }
            sup_by_value[pid]['count'] += 1
            sup_by_value[pid]['value'] += oc.total or 0
        top_suppliers_by_value = sorted(
            sup_by_value.values(), key=lambda x: x['value'], reverse=True)[:5]
        _total_sup_val = sum(s['value'] for s in sup_by_value.values()) or 1
        for s in top_suppliers_by_value:
            s['pct'] = round(s['value'] / _total_sup_val * 100)

        # --- DISTRIBUCIÓN POR ESTADO ---
        _dist_states = [
            ('in_shopping',                        'En Compras',     '#4361ee'),
            ('sent',                               'Enviado',        '#2a9d8f'),
            ('pending_project_approval',           'Pend. Proyecto', '#f4a261'),
            ('pending_purchase_approval',          'Pend. Compras',  '#e9c46a'),
            ('pending_advisory_committee_approval', 'Pend. Comité',   '#e63946'),
        ]
        state_dist = []
        for st, label, color in _dist_states:
            cnt = SDC.search_count(sdc_domain + [('state', '=', st)])
            if cnt > 0:
                state_dist.append(
                    {'state': st, 'label': label, 'count': cnt, 'color': color})

        # --- EFICIENCIA (solo SDC de tipo proyecto — las admin no pasan por compras) ---
        proj_domain = sdc_domain + [('category', '=', 'project')]
        sdc_proj_total = SDC.search_count(proj_domain)
        sdc_proj_converted = SDC.search_count(
            proj_domain + [('state', '=', 'order_created')])
        conversion_rate = round(sdc_proj_converted /
                                sdc_proj_total * 100) if sdc_proj_total else 0

        oc_this_month = OC.search(
            oc_domain + [('create_date', '>=', month_cur)])
        oc_count_month = len(oc_this_month)
        oc_value_month = sum(oc_this_month.mapped('total'))

        completed = SDC.search(
            proj_domain + [('state', '=', 'order_created')], limit=100)
        days_list = []
        for r in completed:
            if r.write_date and r.create_date:
                wd = r.write_date.date() if hasattr(r.write_date, 'date') else r.write_date
                cd = r.create_date.date() if hasattr(r.create_date, 'date') else r.create_date
                diff = (wd - cd).days
                if 0 <= diff <= 365:
                    days_list.append(diff)
        avg_days = round(sum(days_list) / len(days_list)) if days_list else 0

        # --- DISTRIBUCIÓN OC POR ESTADO ---
        oc_sent_ct = OC.search_count(oc_domain + [('state', '=', 'sent')])
        oc_caused_ct = OC.search_count(oc_domain + [('state', '=', 'caused')])
        oc_paid_ct = OC.search_count(oc_domain + [('state', '=', 'paid')])
        oc_total_ct = oc_sent_ct + oc_caused_ct + oc_paid_ct or 1
        oc_state_dist = [
            {'state': 'sent',   'label': 'Enviado',  'count': oc_sent_ct,
             'color': '#4361ee', 'pct': round(oc_sent_ct / oc_total_ct * 100)},
            {'state': 'caused', 'label': 'Causado',  'count': oc_caused_ct,
             'color': '#f4a261', 'pct': round(oc_caused_ct / oc_total_ct * 100)},
            {'state': 'paid',   'label': 'Pagado',   'count': oc_paid_ct,
             'color': '#2a9d8f', 'pct': round(oc_paid_ct / oc_total_ct * 100)},
        ]

        # Valor OC mes anterior (para comparativa de eficiencia)
        prev_month_start_ch = month_cur - relativedelta(months=1)
        oc_prev_month_ch = OC.search(oc_domain + [
            ('create_date', '>=', prev_month_start_ch),
            ('create_date', '<', month_cur),
        ])
        oc_value_prev_month = sum(oc_prev_month_ch.mapped('total'))

        return {
            'monthly_trend': monthly_trend,
            'top_projects': top_projects_enriched,
            'top_suppliers': top_suppliers_by_value,
            'state_dist': state_dist,
            'oc_state_dist': oc_state_dist,
            'efficiency': {
                'conversion_rate': conversion_rate,
                'avg_days': avg_days,
                'oc_count_month': oc_count_month,
                'oc_value_month': oc_value_month,
                'oc_value_prev_month': oc_value_prev_month,
            },
        }

    @api.model
    def get_trends_by_range(self, sdc_from=None, sdc_to=None, oc_from=None, oc_to=None):
        from dateutil.relativedelta import relativedelta

        SDC = self.env['request.quotation']
        OC = self.env['purchase.management.order']

        sdc_domain = []
        oc_domain = []

        def _months_between(from_str, to_str):
            d_from = fields.Date.from_string(from_str).replace(day=1)
            d_to = fields.Date.from_string(to_str)
            months, cur = [], d_from
            while cur <= d_to:
                nxt = cur + relativedelta(months=1)
                months.append((cur, nxt))
                cur = nxt
            return months

        sdc_monthly = []
        if sdc_from and sdc_to:
            for m_start, m_end in _months_between(sdc_from, sdc_to):
                cnt = SDC.search_count(sdc_domain + [
                    ('create_date', '>=', m_start),
                    ('create_date', '<', m_end),
                ])
                sdc_monthly.append(
                    {'month': m_start.strftime('%b %Y'), 'count': cnt})

        oc_monthly = []
        if oc_from and oc_to:
            for m_start, m_end in _months_between(oc_from, oc_to):
                ocs = OC.search(oc_domain + [
                    ('create_date', '>=', m_start),
                    ('create_date', '<', m_end),
                ])
                oc_monthly.append({
                    'month': m_start.strftime('%b %Y'),
                    'count': len(ocs),
                    'total': sum(ocs.mapped('total')),
                })

        return {'sdc_monthly': sdc_monthly, 'oc_monthly': oc_monthly}

    @api.model
    def search_sdc_for_dashboard(self, query):
        from odoo import fields as _f
        today = fields.Date.context_today(self)
        _LABELS = {
            'draft': 'Borrador', 'in_shopping': 'En Compras', 'sent': 'Enviado',
            'pending_project_approval': 'Pend. Aprobación Proy.',
            'pending_purchase_approval': 'Pend. Aprobación Compras',
            'pending_advisory_committee_approval': 'Pend. Comité Asesor',
            'approved': 'Aprobado', 'order_created': 'Orden Creada', 'cancelled': 'Cancelado',
        }
        domain = ['|', '|',
                  ('reference', 'ilike', query),
                  ('subject', 'ilike', query),
                  ('project_id.name', 'ilike', query),
                  ]
        records = self.search(domain, order='create_date desc', limit=50)
        return [{
            'id': r.id,
            'reference': r.reference or '',
            'subject': (r.subject or '')[:45],
            'state': r.state,
            'state_label': _LABELS.get(r.state, r.state),
            'deadline': r.deadline.strftime('%d/%m/%Y') if r.deadline else '',
            'project': r.project_id.name if r.project_id else '',
            'days_left': (r.deadline - today).days if r.deadline else None,
        } for r in records]

    @api.model
    def get_trm_history(self, months=6):
        from dateutil.relativedelta import relativedelta
        today = fields.Date.today()
        month_start = today.replace(day=1)
        Rate = self.env['res.currency.rate']
        result = {}
        for code in ['USD', 'EUR']:
            curr = self.env['res.currency'].search(
                [('name', '=', code), ('active', '=', True)], limit=1)
            if not curr:
                continue
            history = []
            for i in range(months - 1, -1, -1):
                m_start = month_start - relativedelta(months=i)
                m_end = m_start + relativedelta(months=1)
                rates = Rate.search([
                    ('currency_id', '=', curr.id),
                    ('name', '>=', m_start),
                    ('name', '<', m_end),
                ], order='name asc')
                if rates:
                    avg_rate = sum(r.rate for r in rates) / len(rates)
                    cop_value = round(1.0 / avg_rate, 2) if avg_rate else 0
                else:
                    cop_value = round(1.0 / curr.rate, 2) if curr.rate else 0
                history.append(
                    {'month': m_start.strftime('%b %Y'), 'value': cop_value})
            current = round(1.0 / curr.rate, 2) if curr.rate else 0
            result[code] = {'history': history,
                            'current': current, 'symbol': curr.symbol or code}
        return result

    @api.model
    def get_purchase_team_members(self):
        """Retorna integrantes del equipo de Compras para el filtro del dashboard."""
        team = self.env['purchase.team'].search(
            [('name', '=', 'Compras')], limit=1)
        if not team:
            return {'members': [], 'current_member_id': False}

        # Encontrar el purchase.member del usuario en sesión
        current_member_id = False
        emp = self.env.user.employee_id
        if emp:
            m = self.env['purchase.member'].search([
                ('employee_id', '=', emp.id),
                ('team_id', '=', team.id),
            ], limit=1)
            if m:
                current_member_id = m.id

        members = []
        for m in team.member_ids.sorted(key=lambda r: r.employee_id.name or ''):
            members.append({
                'id': m.id,
                'name': m.employee_id.name if m.employee_id else '(Sin nombre)',
                'initials': ''.join(
                    w[0].upper() for w in (m.employee_id.name or '?').split()[:2]
                ),
            })

        return {
            'members': members,
            'current_member_id': current_member_id,
        }

    @api.model
    def create_dashboard_nav_filter(self, model, domain, name):
        """Crea o actualiza ir.filters personal para navegación desde dashboard.
        Usa formato Python repr (tuplas) — Odoo safe_eval lo requiere correctamente.
        is_default=True → SearchModel lo activa como chip removible.
        """
        Filter = self.env['ir.filters']

        # Convertir domain de listas a tuplas — formato estándar Odoo
        def to_tuples(d):
            result = []
            for item in d:
                if isinstance(item, (list, tuple)) and len(item) == 3:
                    result.append(tuple(item))
                else:
                    result.append(item)
            return result

        domain_tuples = to_tuples(domain)
        domain_str = repr(domain_tuples)

        existing = Filter.search([
            ('name', '=', name),
            ('model_id', '=', model),
            ('user_id', '=', self.env.user.id),
        ], limit=1)
        if existing:
            existing.write({'domain': domain_str, 'is_default': True})
        else:
            Filter.create({
                'name': name,
                'model_id': model,
                'domain': domain_str,
                'context': '{}',
                'sort': '[]',
                'user_id': self.env.user.id,
                'is_default': True,
            })
