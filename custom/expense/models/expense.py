# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup
import datetime
from holidays import country_holidays
from ..utils.utils import (
    convert_first_letter_to_uppercase,
    get_accounting_team_emails,
    get_team_emails,
    get_treasury_team_emails,
    calculate_total_requested_amount,
    send_expense_mail,
    get_expense_evidence_and_reimbursement
)


class ExpenseExpense(models.Model):
    _name = 'expense.expense'
    _description = 'Solicitud'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reference'
    _order = 'reference desc'

    """ONE2MANY"""
    displacement_ids = fields.One2many(
        'expense.displacement', 'expense_id', string='Desplazamientos', copy=False)
    """MANY2ONE"""
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', copy=False, domain="[('blocked', '=', False)]")
    partner_id = fields.Many2one(
        'res.partner', string='Contacto', domain="[('is_employee', '=', True)]", copy=False)
    project_id = fields.Many2one(
        'project.management', string='Proyecto', required=True, copy=False, domain="[('prefix', '!=', False)]")
    category_id = fields.Many2one(
        'expense.category', string='Categoría', required=True, copy=False)
    enterprise_id = fields.Many2one(
        'expense.enterprise', string='Empresa', readonly=True, copy=False)
    """CHAR"""
    reference = fields.Char(string='Referencia', required=True, copy=False, readonly=True, index=True,
                            default=lambda self: _('Nuevo'))
    subject = fields.Char(string='Asunto', required=True, copy=False)
    display_name = fields.Char(
        string='Nombre a Mostrar', compute='_compute_display_name', store=True)
    display_user = fields.Char(
        string='Empleado o Contacto', compute='_compute_display_user', store=True)
    """TEXT"""
    observation = fields.Text(string='Observaciones',
                              copy=False, required=True)
    """SELECTION"""
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Pendiente por Aprobar'),
        ('approved', 'Aprobado'),
        ('to_legalize', 'Pendiente por Legalizar'),
        ('paid', 'Pagado'),
        ('legalized', 'Legalizado'),
        ('approved_evidence', 'Evidencia Aprobada'),
        ('caused', 'Causado'),
        ('finalized', 'Finalizado'),
        ('cancelled', 'Cancelado'),
    ], string='Estado', default='draft', required=True, readonly=True, copy=False,)
    """DATE"""
    creation_date = fields.Date(
        string='Fecha de creación', copy=False, default=fields.Date.context_today, required=True,)
    """FLOAT"""
    requested_amount = fields.Float(
        string='Total Solicitado', digits=(16, 0), readonly=True, compute='update_requested_amount', store=True)
    legalized_amount = fields.Float(
        string='Total Legalizado', digits=(16, 0), readonly=True, copy=False)
    approved_amount = fields.Float(
        string='Total Aprobado', digits=(16, 0), readonly=True, copy=False)
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)
    rejected = fields.Boolean(
        string='Rechazado', default=False, readonly=True, copy=False)
    attached_evidence = fields.Boolean(
        string='Evidencia Adjunta', default=False, readonly=True, copy=False)
    attached_reimbursement = fields.Boolean(
        string='Reembolso Adjunto', default=False, readonly=True, copy=False)

    @api.depends('employee_id', 'partner_id')
    def _compute_display_user(self):
        for record in self:
            if record.employee_id:
                record.display_user = record.employee_id.name
            elif record.partner_id:
                record.display_user = record.partner_id.name
            else:
                record.display_user = 'Sin Empleado'

    @api.depends('subject', 'reference')
    def _compute_display_name(self):
        for record in self:
            if record.reference == 'Nuevo':
                record.display_name = record.subject
            else:
                record.display_name = record.reference

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        today_dt = (
            datetime.datetime.strptime(today, "%Y-%m-%d").date()
            if isinstance(today, str) else today
        )
        if today_dt.weekday() >= 5:  # 5=sábado, 6=domingo
            raise ValidationError(_(
                "No se pueden crear solicitudes los fines de semana. "
                "Por favor, intente nuevamente en un día hábil."
            ))
        co_holidays = country_holidays(
            "CO", years=today_dt.year, observed=True)
        if today_dt in co_holidays:
            raise ValidationError(_(
                "No se pueden crear solicitudes en días festivos. "
                "Por favor, intente nuevamente en un día hábil que no sea festivo."
            ))

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['subject'] = convert_first_letter_to_uppercase(
                vals.get('subject', ''))
            vals['observation'] = convert_first_letter_to_uppercase(
                vals.get('observation', ''))
            """Elimina el contacto o empleado, dependiendo la categoria"""
            if 'category_id' in vals and vals['category_id']:
                if vals['category_id'] == 1:  # Tiquetes
                    vals['employee_id'] = False
                elif vals['category_id'] == 2:  # Viáticos
                    vals['partner_id'] = False
            """Valida que la fecha de creación no sea diferente a la actual"""
            if 'creation_date' in vals:
                creation_date = vals['creation_date']
                today = fields.Date.context_today(self)
                if isinstance(creation_date, str):
                    creation_date = datetime.datetime.strptime(
                        creation_date, "%Y-%m-%d").date()
                if isinstance(today, str):
                    today = datetime.datetime.strptime(
                        today, "%Y-%m-%d").date()
                if creation_date != today:
                    raise ValidationError(
                        _("La fecha de creación no puede ser diferente a la fecha actual. Fecha ingresada: %s, Fecha actual: %s") % (
                            vals['creation_date'], fields.Date.context_today(
                                self)
                        )
                    )
        records = super(ExpenseExpense, self).create(vals_list)
        if records:
            records._notify_avatar_update(reason="create")
        return records

    def write(self, vals):
        """Si hay cambio de categoría y existen desplazamientos, limpiar todo"""
        previous_employees = {}
        if 'employee_id' in vals:
            previous_employees = {record.id: record.employee_id.id for record in self}
        if 'category_id' in vals:
            old_category = self.category_id.id if self.category_id else None
            new_category = vals['category_id']
            if old_category and new_category and old_category != new_category and self.displacement_ids:
                old_category_name = self.category_id.name if self.category_id else 'Sin categoría'
                new_category_obj = self.env['expense.category'].browse(
                    new_category)
                new_category_name = new_category_obj.name if new_category_obj else 'Sin categoría'
                self.write({
                    'displacement_ids': [(6, 0, [])],
                    'employee_id': False,
                    'partner_id': False
                })
                self.message_post(
                    body=Markup(
                        f"<span>Se cambió la categoría de <span style='color: #ef4444;'>{old_category_name}</span> a "
                        f"<span style='color: #017e84;'>{new_category_name}</span>. Se eliminaron todos los "
                        f"desplazamientos existentes para mantener la integridad de los datos.</span>"
                    )
                )
        if 'observation' in vals:
            vals['observation'] = convert_first_letter_to_uppercase(
                vals.get('observation', ''))
        if 'subject' in vals:
            vals['subject'] = convert_first_letter_to_uppercase(
                vals.get('subject', ''))
        """No permite hacer cambios en los campos si el estado del gasto es diferente a 'draft'."""
        for record in self:
            """Solo aplica a permisos diferentes de administrador."""
            admin = self.env.user.has_group('expense.group_manager_expense')
            if not admin:
                if record.state != 'draft':
                    non_editable_fields = ['employee_id', 'partner_id', 'project_id',
                                           'category_id', 'subject', 'observation', 'creation_date', 'displacement_ids']
                    for field in non_editable_fields:
                        if field in vals:
                            raise UserError(
                                _('No se pueden realizar cambios en el campo "%s" porque el estado de la solicitud es "%s". Solo se permite editar cuando la solicitud está en estado Borrador.') %
                                (record._fields[field].string,
                                 dict(record._fields['state'].selection).get(record.state, record.state))
                            )
                elif record.rejected and record.state == 'draft':
                    # Cuando esta en rechazado y en estado borrador, solo permitir modificar observaciones y
                    # desplazamientos. El resto de campos permanecen bloqueados.
                    allowed_fields_when_rejected = [
                        'observation', 'displacement_ids', 'state', 'rejected'
                    ]
                    for field in vals:
                        if field not in allowed_fields_when_rejected:
                            raise UserError(
                                _('No se pueden realizar cambios en el campo "%s" cuando la solicitud está rechazada. '
                                  'Solo se permite modificar las observaciones y los desplazamientos para corregir los motivos del rechazo.') %
                                record._fields[field].string
                            )
        res = super(ExpenseExpense, self).write(vals)
        if res and 'employee_id' in vals:
            changed_records = self.filtered(
                lambda record: previous_employees.get(record.id) != record.employee_id.id
            )
            if changed_records:
                changed_records._notify_avatar_update(reason="write")
        return res

    @api.model
    def get_displacement_data(self, expense_id):
        displacements = self.env['expense.displacement'].search_read(
            [['expense_id', '=', expense_id]],
            ['id', 'initial_date', 'final_date', 'origin_id', 'destination_id',
             'service_line_ids', 'write_date', 'category_id', 'ticket_id', 'modality_type']
        )
        all_svc_ids = [sid for d in displacements for sid in d['service_line_ids']]
        service_lines = self.env['expense.service.line'].search_read(
            [['id', 'in', all_svc_ids]],
            ['id', 'service_id', 'total_amount']
        ) if all_svc_ids else []
        service_ids = list({sl['service_id'][0] for sl in service_lines if sl['service_id']})
        services = self.env['expense.service'].search_read(
            [['id', 'in', service_ids]], ['id', 'name']
        ) if service_ids else []
        return {
            'displacements': displacements,
            'service_lines': service_lines,
            'services': services,
        }

    @api.model
    def get_displacement_hash(self, expense_id):
        self.env.cr.execute("""
            SELECT
                COALESCE(COUNT(d.id), 0)::text AS disp_count,
                COALESCE(MAX(d.write_date)::text, '') AS disp_max_write,
                COALESCE(COUNT(sl.id), 0)::text AS line_count,
                COALESCE(MAX(sl.write_date)::text, '') AS line_max_write
            FROM expense_displacement d
            LEFT JOIN expense_service_line sl ON sl.displacement_id = d.id
            WHERE d.expense_id = %s
        """, [expense_id])
        row = self.env.cr.dictfetchone()
        return {'hash': ':'.join(row.values())}

    @api.model
    def get_avatar_widget_config(self, record_id=False, field_name=False):
        if field_name != 'employee_id':
            return {}
        channel = f"expense_avatar_{record_id}" if record_id else False
        return {
            "channel_name": channel,
            "notification_type": "expense.avatar/update",
            "payload_key": "expense_id",
        }

    def _notify_avatar_update(self, reason="update"):
        """Notifica al frontend para que actualice la información del avatar."""
        records = self.filtered(lambda record: record.id)
        if not records:
            return
        timestamp = fields.Datetime.now()
        bus = self.env['bus.bus']
        for record in records:
            config = self.get_avatar_widget_config(record.id, 'employee_id')
            channel = config.get('channel_name')
            notification_type = config.get('notification_type', 'avatar/update')
            payload_key = config.get('payload_key', 'record_id')
            if not channel:
                continue
            payload = {
                payload_key: record.id,
                'expense_id': record.id,
                'employee_id': record.employee_id.id or False,
                'reason': reason,
                'timestamp': timestamp,
            }
            bus._sendone(
                channel,
                notification_type,
                payload,
            )

    @api.depends('displacement_ids.service_line_ids.total_amount', 'displacement_ids', 'displacement_ids.service_line_ids')
    def update_requested_amount(self):
        """Actualizar el monto solicitado basado en los servicios de los desplazamientos"""
        for record in self:
            record.requested_amount = calculate_total_requested_amount(
                record.displacement_ids
            )

    @api.constrains('legalized_amount')
    def _check_legalized_amount(self):
        for record in self:
            if record.legalized_amount > record.requested_amount:
                raise ValidationError(
                    _('El monto legalizado no puede ser mayor al monto solicitado. '
                      'Monto solicitado: $%s, Monto legalizado: $%s') %
                    (record.requested_amount, record.legalized_amount)
                )

    @api.constrains('category_id', 'displacement_ids')
    def _check_category_displacement_consistency(self):
        """Validar consistencia entre categoría y desplazamientos"""
        for record in self:
            if record.category_id and record.displacement_ids:
                # Para Viáticos, validar que todos los desplazamientos tengan servicios
                if record.category_id.id == 2:  # Viáticos
                    for displacement in record.displacement_ids:
                        if not displacement.service_line_ids:
                            raise ValidationError(
                                _('Error de consistencia: La categoría "[VIAT] Viáticos (Alimentación, Hospedaje, etc.)" requiere que todos los '
                                  'desplazamientos tengan al menos un servicio asignado. '
                                  'Desplazamiento sin servicios: %s → %s') %
                                (displacement.origin_id.name,
                                 displacement.destination_id.name)
                            )
                # Para Tiquetes, no debería haber servicios
                elif record.category_id.id == 1:  # Tiquetes
                    services_count = sum(len(d.service_line_ids)
                                         for d in record.displacement_ids)
                    if services_count > 0:
                        raise ValidationError(
                            _('Error de consistencia: La categoría "[TIQ] Tiquetes y vuelos" no permite '
                              'servicios en los desplazamientos. Se encontraron %d servicios asignados.') %
                            services_count
                        )
                # Para Tiquetes, no debería haber servicios (esto se maneja automáticamente)
                elif record.category_id.id == 1:  # Tiquetes
                    services_count = sum(len(d.service_line_ids)
                                         for d in record.displacement_ids)
                    if services_count > 0:
                        raise ValidationError(
                            _('Error de consistencia: La categoría "[TIQ] Tiquetes y vuelos" no permite '
                              'servicios en los desplazamientos. Se encontraron %d servicios asignados.') %
                            services_count
                        )
    @api.onchange('category_id')
    def _onchange_category_id(self):
        """Limpiar empleado o contacto dependiendo de la categoría seleccionada"""
        if self.category_id:
            if self.category_id.name == 'Viáticos (Alimentación, Hospedaje, etc.)':
                self.partner_id = False
            elif self.category_id.name == 'Tiquetes y vuelos':
                self.employee_id = False

    def action_send_for_approval(self):
        if len(self.displacement_ids) == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe agregar al menos un desplazamiento para solicitar aprobación. Verifique e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        template_xmlid = 'expense.mail_template_expense_approval'
        if self.category_id.name == 'Viáticos (Alimentación, Hospedaje, etc.)':
            send_expense_mail(
                self,
                template_xmlid,
                get_accounting_team_emails(self),
            )
        elif self.category_id.name == 'Tiquetes y vuelos':
            """Valida que la informacion personal del contacto este completa"""
            partner = self.env['expense.personal.information'].search(
                [('partner_id', '=', self.partner_id.id)], limit=1)
            if not partner or any(not getattr(partner, field) for field in [
                'identification_type_id', 'country_id', 'email', 'phone', 'nuid', 'job_title', 'birth_date'
            ]):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('La información personal del "Contacto" está incompleta. Por favor, haga clic en el icono de advertencia que se encuentra al lado derecho del campo para completarla.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            send_expense_mail(
                self,
                template_xmlid,
                get_team_emails(self),
            )
        """Solicita aprobación del registro"""
        self.sudo().write({'state': 'to_approve', 'rejected': False})
        self.sudo().message_post(
            body=Markup(
                f"<span>Se envió una notificación por correo electrónico <span style='color: #017e84;'>solicitando la aprobación</span> "
                f"del registro. </span>"
            )
        )

    def action_approve(self):
        """Abre wizard de aprobación"""
        if self.state != 'to_approve':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede aprobar una solicitud en estado "Por Aprobar".'),
                    'type': 'danger',
                    'sticky': False,

                }
            }
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_expense_id': self.id, 'default_requested_amount': self.requested_amount}
        }

    def action_pay(self):
        """Paga la solicitud"""
        if self.state != 'approved':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede pagar una solicitud en estado "Aprobado".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.pay.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_expense_id': self.id,
            }
        }

    def action_attach_evidence(self):
        """Abre wizard para adjuntar evidencia del viático"""
        if self.state != 'to_legalize':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede adjuntar evidencia a una solicitud en estado "Por Legalizar".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.attach.evidence.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_expense_id': self.id}
        }

    def action_reimburse(self):
        """Reembolsa el viático"""
        if self.state != 'to_legalize':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede reembolsar una solicitud en estado "Por Legalizar".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.attach.reimburse.evidence.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_expense_id': self.id, }
        }

    def action_approve_legalization(self):
        """Abre wizard para aprobar legalización del viático"""
        if self.state != 'legalized':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede aprobar la legalización de una solicitud en estado "Legalizado".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        # Buscar evidencias y mantener solo la más reciente
        evidence_attachments = self.env['ir.attachment'].search([
            ('res_id', '=', self.id),
            ('res_model', '=', 'expense.expense'),
            ('description', '=', 'Evidencia de la solicitud')
        ], order='create_date desc')
        if len(evidence_attachments) > 1:
            evidence_attachments[1:].sudo().unlink()
        # Buscar reembolsos y mantener solo el más reciente
        reimbursement_attachments = self.env['ir.attachment'].search([
            ('res_id', '=', self.id),
            ('res_model', '=', 'expense.expense'),
            ('description', '=', 'Evidencia del reembolso')
        ], order='create_date desc')
        if len(reimbursement_attachments) > 1:
            reimbursement_attachments[1:].sudo().unlink()
        # Usar función auxiliar para obtener evidencia y reembolso
        evidence, reimbursement = get_expense_evidence_and_reimbursement(self)
        wizard = self.env['expense.approve.legalization.wizard'].sudo().create({
            'expense_id': self.id,
            'attached_evidence': evidence,
            'attached_reimbursement': reimbursement
        })
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.approve.legalization.wizard',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id
        }

    def action_view_attached_evidence(self):
        """Abre la evidencia adjunta del viático"""
        if not self.attached_evidence and not self.attached_reimbursement:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No hay evidencia adjunta para esta solicitud. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        evidence, reimbursement = get_expense_evidence_and_reimbursement(self)
        wizard = self.env['expense.view.attachment'].sudo().create({
            'expense_id': self.id,
            'attached_evidence': evidence,
            'attached_reimbursement': reimbursement,
            'view_mode': 'evidence' if evidence else 'reimbursement',
            'evidence': bool(evidence),
            'reimbursement': bool(reimbursement)
        })
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.view.attachment',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id,
        }

    def action_cause_request(self):
        """Causa el viático"""
        if self.state != 'approved_evidence':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede causar una solicitud cuando las evidencias han sido aprobadas. Verifique el estado actual e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        self.sudo().write({'state': 'caused'})
        self.sudo().message_post(
            body=Markup(
                f"<span>La solicitud fue <span style='color: #017e84;'>causada</span>.</span>"
            )
        )

    def action_close_request(self):
        """Cierra el viático"""
        if self.state != 'caused':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede finalizar una solicitud en estado "Causado".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        self.sudo().write({'state': 'finalized', 'active': False})
        self.sudo().message_post(
            body=Markup(
                f"<span>La solicitud fue <span style='color: #017e84;'>finalizada</span>.</span>"
            )
        )

    def action_cancel(self):
        """Cancela el viático"""
        if self.state in ['to_legalize', 'legalized', 'authorized', 'caused', 'finalized']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se puede cancelar una solicitud en estado "%s".') % self.state,
                    'type': 'danger',
                    'sticky': False,
                }
            }
        self.sudo().write({'state': 'cancelled', 'active': False})
        self.sudo().message_post(
            body=Markup(
                f"<span>La solicitud fue <span style='color: #017e84;'>cancelada</span>.</span>"
            )
        )

    """BOTONES CATEGORIA TIQUETES Y VUELOS"""

    def action_approve_ticket(self):
        template_approval_xmlid = 'expense.mail_template_expense_approval_full'
        template_treasury_xmlid = 'expense.mail_template_expense_pending_to_be_paid'
        if self.state != 'to_approve':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede procesar un tiquete si se encuentra en el estado "Pendiente por Aprobar".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        project = self.env['project.management'].search(
            [('id', '=', self.project_id.id)], limit=1).prefix
        if not project:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se encontró el proyecto asociado al tiquete. Por favor, comuniquese con el area de soporte tecnico'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        self.sudo().write({
            'state': 'approved',
            'reference': 'TIQ/' + project + self.env['ir.sequence'].next_by_code('expense.category.ticket'),
        })
        treasury_emails = get_treasury_team_emails(self)
        send_expense_mail(
            self,
            template_approval_xmlid,
            [self.create_uid.email],
            cc=treasury_emails,
        )
        send_expense_mail(
            self,
            template_treasury_xmlid,
            treasury_emails,
        )
        self.sudo().message_post(
            body=Markup(
                f"<span>El tiquete fue <span style='color: #017e84;'>aprobado</span>.</span>"
            )
        )

    def action_reject_ticket(self):
        if self.state not in ['to_approve', 'approved']:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede rechazar un tiquete si se encuentra en el estado "Pendiente por Aprobar".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_expense_id': self.id, 'default_reject': True}
        }

    def action_pay_ticket(self):
        if self.state != 'approved':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede pagar un tiquete si se encuentra en el estado "Aprobado".'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.pay.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_expense_id': self.id}
        }

    def send_pending_legalization_mail(self):
        """Envía el correo de legalización pendiente a los empleados"""
        # Obtener la URL base del sistema
        base_url = self.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url', '')
        # Validar si la URL corresponde a producción
        if base_url != 'http://38.52.158.27':
            return  # No enviar correos en desarrollo, staging, etc.
        viaticos_category = self.env['expense.category'].search(
            [('name', '=', 'Viáticos (Alimentación, Hospedaje, etc.)')], limit=1)
        if not viaticos_category:
            return
        expenses = self.search([
            ('category_id', '=', viaticos_category.id),
            ('state', '=', 'to_legalize'),
            ('active', '=', True),
            ('employee_id', '!=', False)
        ])
        template = self.env.ref(
            'expense.mail_template_expense_pending_legalization')
        for expense in expenses:
            template.send_mail(expense.id, force_send=True)
