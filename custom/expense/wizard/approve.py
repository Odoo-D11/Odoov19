from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase, send_expense_mail, get_treasury_team_emails


class ExpenseApproveWizardService(models.TransientModel):
    _name = 'expense.approve.wizard.service'
    _description = 'Servicios de la solicitud'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    approve_wizard_id = fields.Many2one(
        'expense.approve.wizard', string='Aprobar solicitud', ondelete='cascade')
    service_id = fields.Many2one(
        'expense.service', string='Servicio', required=True)
    """FLOAT"""
    quantity = fields.Float(string='Cantidad', digits=(16, 0), required=True)
    unit_price = fields.Float(string='Precio Unit.',
                              digits=(16, 0), required=True)
    subtotal = fields.Float(string='Subtotal', digits=(
        16, 0), compute='_compute_subtotal', readonly=True)
    total_amount = fields.Float(string='Total', digits=(16, 0), readonly=True)

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.quantity * record.unit_price


class ExpenseApproveWizard(models.TransientModel):
    _name = 'expense.approve.wizard'
    _description = 'Aprobar solicitud'
    _transient_max_count = 100
    _transient_max_hours = 24

    """ONE2MANY"""
    service_ids = fields.One2many(
        'expense.approve.wizard.service', 'approve_wizard_id', string='Servicios')
    """MANY2ONE"""
    expense_id = fields.Many2one(
        'expense.expense', required=True, readonly=True, string='Solicitud', ondelete='cascade')
    displacement_id = fields.Many2one(
        'expense.displacement', string='Desplazamiento', domain="[('expense_id', '=', expense_id)]")
    rejection_reason_id = fields.Many2one(
        'expense.rejection.reason', string='Motivo')
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', related='expense_id.employee_id', readonly=True)
    enterprise_id = fields.Many2one('expense.enterprise', string='Empresa')
    category_id = fields.Many2one(
        'expense.category', string='Categoría', related='expense_id.category_id', readonly=True)
    """FLOAT"""
    approved_amount = fields.Float(string='Monto aprobado', digits=(16, 0))
    requested_amount = fields.Float(
        string='Monto solicitado', readonly=True, digits=(16, 0))
    bag = fields.Float(string='Bolsa', digits=(
        16, 0), related='employee_id.bag')
    """INTEGER"""
    pending_request = fields.Integer(
        string='Solicitudes pendientes', compute='_compute_pending_requests', readonly=True)
    """TEXT"""
    justification = fields.Text(string='Justificación')
    rejection_justification = fields.Text(string='Justificación de rechazo')
    temp_services_data = fields.Text(
        string='Datos temporales de servicios', help='JSON con servicios editados y confirmados por desplazamiento')
    """BOOLEAN"""
    establish_company = fields.Boolean(
        string='Establecer empresa', readonly=True)
    edit_value = fields.Boolean(readonly=True)
    reject = fields.Boolean(readonly=True)
    show_edit_instructions = fields.Boolean(
        string='Mostrar instrucciones de edición', readonly=True)
    show_displacement_editing = fields.Boolean(
        string='Mostrar edición de desplazamientos', readonly=True)
    simple_approve = fields.Boolean(
        string='Aprobación simple sin edición', readonly=True)

    @api.onchange('displacement_id')
    def _onchange_displacement_id(self):
        if self.displacement_id and self.edit_value:
            # Cargar servicios del desplazamiento seleccionado
            self._load_services_from_temp_or_original()

            # Calcular el total
            self._compute_approved_amount()
        elif not self.displacement_id:
            self.service_ids = [(5, 0, 0)]
            self.approved_amount = 0.0

    @api.onchange('service_ids')
    def _onchange_service_ids(self):
        """Recalcula el monto cuando cambian los servicios"""
        if self.edit_value and self.displacement_id:
            self._compute_approved_amount()

    @api.depends('expense_id')
    def _compute_pending_requests(self):
        for record in self:
            record.pending_request = self.env['expense.expense'].search_count([
                ('state', '=', 'to_approve'), ('category_id',
                                               '=', record.expense_id.category_id.id),
                ('id', '!=', record.expense_id.id)
            ])

    @api.depends('service_ids.subtotal', 'temp_services_data')
    def _compute_approved_amount(self):
        """Calcula el monto aprobado basado en todos los servicios editados"""
        for record in self:
            if record.edit_value:
                # Calcular total considerando todos los desplazamientos
                record.approved_amount = record._calculate_total_approved_amount()
            elif not record.edit_value:
                record.approved_amount = record.requested_amount

    @api.depends('temp_services_data', 'show_displacement_editing')
    def _compute_can_proceed_to_next_step(self):
        """Determina si se puede proceder al siguiente paso"""
        for record in self:
            record.can_proceed_to_next_step = (
                record.show_displacement_editing and
                bool(record.temp_services_data)
            )

    def action_back_to_instructions(self):
        """Volver al paso anterior según el contexto actual"""
        if self.establish_company and not self.simple_approve:
            # Paso 3 → Paso 2: Empresa → Edición desplazamientos (solo si venimos de editar)
            self.establish_company = False
            self.show_displacement_editing = True
            # Limpiar campo de desplazamiento y servicios al volver a la vista
            self.displacement_id = False
            self.service_ids = [(5, 0, 0)]
        elif self.establish_company and self.simple_approve:
            # Volver de aprobación simple al menú principal
            self._reset_all_fields()
        elif self.show_displacement_editing:
            # Paso 2 → Paso 1: Edición → Instrucciones
            self.show_displacement_editing = False
            self.show_edit_instructions = True
        else:
            # Volver al menú principal y resetear todos los campos
            self._reset_all_fields()

        return self._reload_wizard()

    def _reset_all_fields(self):
        """Resetea todos los campos del wizard"""
        self.edit_value = False
        self.show_edit_instructions = False
        self.show_displacement_editing = False
        self.establish_company = False
        self.simple_approve = False
        self.reject = False
        self.enterprise_id = False
        self.displacement_id = False
        self.temp_services_data = False
        self.justification = False
        self.approved_amount = 0.0
        self.service_ids = [(5, 0, 0)]

    def _reload_wizard(self):
        """Recarga el wizard con los valores actuales"""
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.approve.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_approve_request(self):
        template_partial_xmlid = 'expense.mail_template_expense_approval_partial'
        template_full_xmlid = 'expense.mail_template_expense_approval_full'

        if not self.enterprise_id:
            if not self.establish_company and not self.edit_value and not self.simple_approve:
                # Primera vez que se presiona Aprobar - mostrar solo empresa
                self.simple_approve = True
                self.establish_company = True
                return self._reload_wizard()
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Debe seleccionar una empresa responsable del pago. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

        if self.edit_value:
            # Validar que al menos se haya editado un desplazamiento
            if not self.temp_services_data:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Debe confirmar los cambios en al menos un desplazamiento antes de aprobar.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            if self.approved_amount <= 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('El monto aprobado debe ser mayor a cero. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            elif self.approved_amount > self.requested_amount:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('El monto aprobado no puede ser mayor al monto solicitado. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            elif not self.justification:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Debe proporcionar una justificación para la aprobación. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

            # Registrar cambios en las notas de la solicitud ANTES de actualizar
            self._log_displacement_changes()

            # Actualizar todos los servicios editados
            self._update_all_displacement_services()
            send_expense_mail(
                self.expense_id,
                template_partial_xmlid,
                [self.expense_id.create_uid.email],
                approved_amount=self.approved_amount,
                justification=convert_first_letter_to_uppercase(
                    self.justification.replace('\n', ' ')
                ),
                enterprise_id=self.enterprise_id.name,
            )
            self.expense_id.sudo().write(
                {'approved_amount': self.approved_amount})
            self.expense_id.sudo().message_post(
                body=Markup(
                    _(
                        "<span>La solicitud fue aprobada por un valor de $<span style='color: #017e84;'>%s</span>. Justificación: <span style='color: #017e84;'>%s</span>.</span>"
                    ) % ("{:,.0f}".format(self.approved_amount).replace(',', '.'), convert_first_letter_to_uppercase(self.justification.replace('\n', ' ')))
                )
            )
        else:
            send_expense_mail(
                self.expense_id,
                template_full_xmlid,
                [self.expense_id.create_uid.email],
                enterprise_id=self.enterprise_id.name,
            )
            self.expense_id.sudo().message_post(
                body=Markup(
                    _(
                        "<span>La solicitud fue <span style='color: #017e84;'>aprobada</span> correctamente.</span>"
                    )
                )
            )
        self.expense_id.sudo().write({
            'state': 'approved',
            'reference': 'VIAT/' + self.enterprise_id.prefix + self.env['ir.sequence'].next_by_code('expense.category.viatic'),
            'enterprise_id': self.enterprise_id.id,
        })
        send_expense_mail(
            self.expense_id,
            'expense.mail_template_expense_pending_to_be_paid',
            get_treasury_team_emails(self),
            enterprise_id=self.enterprise_id.name,
        )

    def action_edit_value(self):
        self.edit_value = True
        self.show_edit_instructions = True
        self.show_displacement_editing = False
        self.reject = False
        return self._reload_wizard()

    def action_show_reject(self):
        self.edit_value = False
        self.reject = True
        return self._reload_wizard()

    def action_reject(self):
        if not self.rejection_reason_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe seleccionar un motivo de rechazo. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        if not self.rejection_justification:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe proporcionar una justificación para el rechazo. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        send_expense_mail(
            self.expense_id,
            'expense.mail_template_expense_approval_rejected',
            [self.expense_id.create_uid.email],
            reason=self.rejection_reason_id.name,
            justification=convert_first_letter_to_uppercase(
                self.rejection_justification.replace('\n', ' ')
            ),
        )
        self.expense_id.sudo().write({
            'state': 'draft',
            'rejected': True
        })
        self.expense_id.sudo().message_post(
            body=Markup(
                _(
                    "<span>La solicitud fue <span style='color: #017e84;'>rechazada</span> por el motivo: <span style='color: #017e84;'>%s</span> y "
                    "con la justificación: <span style='color: #017e84;'>%s</span>.<span>"
                ) % (self.rejection_reason_id.name, convert_first_letter_to_uppercase(self.rejection_justification.replace('\n', ' ')))
            )
        )

    def action_confirm_displacement_changes(self):
        """Confirma los cambios del desplazamiento actual y los guarda en temp_services_data"""
        if not self.displacement_id or not self.service_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe seleccionar un desplazamiento y agregar al menos un servicio antes de confirmar.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }

        # Validar que todos los servicios tengan datos válidos
        for service in self.service_ids:
            if not service.service_id or service.quantity <= 0 or service.unit_price <= 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Todos los servicios deben tener un servicio válido, cantidad mayor a 0 y precio mayor a 0.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }

        # Verificar si hay cambios reales
        if not self._has_displacement_changes():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No se detectaron cambios en los servicios del desplazamiento.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

        # Guardar en datos temporales
        self._save_current_services_to_temp()

        # Recalcular monto total
        self._compute_approved_amount()

        # Mostrar mensaje de éxito
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Éxito'),
                'message': _('Los cambios del desplazamiento han sido confirmados correctamente.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_next_to_displacement_editing(self):
        """Ir al paso de edición de desplazamientos"""
        self.show_edit_instructions = False
        self.show_displacement_editing = True
        # Limpiar campo de desplazamiento y servicios al entrar a la vista
        self.displacement_id = False
        self.service_ids = [(5, 0, 0)]
        return self._reload_wizard()

    def action_next_to_final_approval(self):
        """Ir al paso final de aprobación (empresa y justificación)"""
        # Validar que haya datos en temp_services_data
        if not self.temp_services_data:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe confirmar los cambios en al menos un desplazamiento antes de continuar.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }

        # Validar que los datos en temp_services_data sean válidos
        import json
        try:
            temp_data = json.loads(self.temp_services_data)
            if not temp_data or len(temp_data) == 0:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('No hay cambios confirmados válidos para proceder.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
        except (json.JSONDecodeError, TypeError):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Los datos de servicios temporales no son válidos.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }

        self.show_displacement_editing = False
        self.establish_company = True
        return self._reload_wizard()

    def _update_all_displacement_services(self):
        """Actualiza todos los servicios editados desde los datos temporales"""
        import json

        if not self.temp_services_data:
            return

        try:
            temp_data = json.loads(self.temp_services_data)
        except (json.JSONDecodeError, TypeError):
            return

        # Actualizar cada desplazamiento que tenga datos temporales
        for displacement_id_str, services_data in temp_data.items():
            displacement = self.env['expense.displacement'].browse(
                int(displacement_id_str))

            if displacement.exists():
                # Eliminar servicios existentes y crear nuevos
                displacement.service_line_ids.unlink()
                for service_data in services_data:
                    self.env['expense.service.line'].sudo().create({
                        'displacement_id': displacement.id,
                        'service_id': service_data['service_id'],
                        'quantity': service_data['quantity'],
                        'unit_price': service_data['unit_price'],
                    })

    def _save_current_services_to_temp(self):
        """Guarda los servicios actuales en el campo temporal JSON"""
        import json

        if not self.displacement_id or not self.service_ids:
            return

        # Obtener datos temporales existentes
        temp_data = {}
        if self.temp_services_data:
            try:
                temp_data = json.loads(self.temp_services_data)
            except (json.JSONDecodeError, TypeError):
                temp_data = {}

        # Guardar servicios del desplazamiento actual
        displacement_key = str(self.displacement_id.id)
        temp_data[displacement_key] = [{
            'service_id': service.service_id.id,
            'quantity': service.quantity,
            'unit_price': service.unit_price,
        } for service in self.service_ids]

        self.temp_services_data = json.dumps(temp_data)

    def _load_services_from_temp_or_original(self):
        """Carga servicios desde datos temporales o desde el desplazamiento original"""
        import json

        if not self.displacement_id:
            return

        self.service_ids = [(5, 0, 0)]  # Limpiar servicios actuales

        # Intentar cargar desde datos temporales primero
        displacement_key = str(self.displacement_id.id)
        temp_data = {}

        if self.temp_services_data:
            try:
                temp_data = json.loads(self.temp_services_data)
            except (json.JSONDecodeError, TypeError):
                temp_data = {}

        if displacement_key in temp_data:
            # Cargar desde datos temporales (servicios ya editados y confirmados)
            services_to_add = []
            for service_data in temp_data[displacement_key]:
                services_to_add.append((0, 0, {
                    'service_id': service_data['service_id'],
                    'quantity': service_data['quantity'],
                    'unit_price': service_data['unit_price'],
                }))
            self.service_ids = services_to_add
        else:
            # Cargar desde el desplazamiento original (servicios sin editar)
            services_to_add = []
            for service in self.displacement_id.service_line_ids:
                services_to_add.append((0, 0, {
                    'service_id': service.service_id.id,
                    'quantity': service.quantity,
                    'unit_price': service.unit_price,
                }))
            self.service_ids = services_to_add

    def _calculate_total_approved_amount(self):
        """Calcula el monto total aprobado considerando todos los desplazamientos editados"""
        import json

        total = 0.0
        edited_displacement_ids = []

        # Calcular basado en datos temporales confirmados
        if self.temp_services_data:
            try:
                temp_data = json.loads(self.temp_services_data)
                edited_displacement_ids = [
                    int(disp_id) for disp_id in temp_data.keys()]
                for services in temp_data.values():
                    for service_data in services:
                        total += service_data['quantity'] * \
                            service_data['unit_price']
            except (json.JSONDecodeError, TypeError):
                pass

        # Agregar servicios del desplazamiento actual si no está confirmado
        if (self.displacement_id and self.service_ids and
                not self._is_displacement_confirmed()):
            for service in self.service_ids:
                total += service.subtotal

        # Agregar desplazamientos no editados
        for displacement in self.expense_id.displacement_ids:
            if (displacement.id not in edited_displacement_ids and
                    displacement.id != (self.displacement_id.id if self.displacement_id else 0)):
                for service in displacement.service_line_ids:
                    total += service.total_amount

        return total

    def _is_displacement_confirmed(self):
        """Verifica si el desplazamiento actual ha sido confirmado en temp_services_data"""
        import json

        if not self.displacement_id or not self.temp_services_data:
            return False

        try:
            temp_data = json.loads(self.temp_services_data)
            return str(self.displacement_id.id) in temp_data
        except (json.JSONDecodeError, TypeError):
            return False

    def _has_displacement_changes(self):
        """Verifica si hay cambios reales en los servicios del desplazamiento actual"""
        if not self.displacement_id:
            return False

        # Obtener servicios originales del desplazamiento
        original_services = []
        for service in self.displacement_id.service_line_ids:
            original_services.append({
                'service_id': service.service_id.id,
                'quantity': service.quantity,
                'unit_price': service.unit_price,
            })

        # Obtener servicios actuales del wizard
        current_services = []
        for service in self.service_ids:
            current_services.append({
                'service_id': service.service_id.id,
                'quantity': service.quantity,
                'unit_price': service.unit_price,
            })

        # Comparar listas de servicios
        return original_services != current_services

    def _log_displacement_changes(self):
        """Registra los cambios realizados en los desplazamientos en las notas de la solicitud"""
        import json
        from datetime import datetime

        if not self.temp_services_data:
            return

        try:
            temp_data = json.loads(self.temp_services_data)
        except (json.JSONDecodeError, TypeError):
            return

        changes_html = []
        changes_html.append(
            "<div style='margin: 15px 0; font-family: Arial, sans-serif; color: #000;'>")
        changes_html.append(
            "<p style='color: #000; margin-bottom: 10px; font-size: 13px; font-weight: normal;'>")
        changes_html.append("A continuación se presentan los servicios editados durante el proceso de aprobación. Los cambios realizados reflejan las modificaciones en cantidades, precios unitarios y totales de cada servicio por desplazamiento.</p>")

        for displacement_id_str, new_services in temp_data.items():
            displacement = self.env['expense.displacement'].browse(
                int(displacement_id_str))

            if not displacement.exists():
                continue

            # Obtener servicios originales ANTES de que se modifiquen
            original_services = []
            for service in displacement.service_line_ids:
                original_services.append({
                    'service_name': service.service_id.name,
                    'quantity': service.quantity,
                    'unit_price': service.unit_price,
                    'total': service.quantity * service.unit_price
                })

            # Preparar servicios nuevos con nombres
            new_services_with_names = []
            for service_data in new_services:
                service_name = self.env['expense.service'].browse(
                    service_data['service_id']).name
                new_services_with_names.append({
                    'service_name': service_name,
                    'quantity': service_data['quantity'],
                    'unit_price': service_data['unit_price'],
                    'total': service_data['quantity'] * service_data['unit_price']
                })

            # Formatear fechas
            initial_date = displacement.initial_date.strftime(
                "%d/%m/%Y") if displacement.initial_date else "N/A"
            final_date = displacement.final_date.strftime(
                "%d/%m/%Y") if displacement.final_date else "N/A"

            # Encabezado del desplazamiento
            changes_html.append("<div style='margin: 10px 0;'>")

            # Fila "DESPLAZAMIENTO"
            changes_html.append(
                "<table style='width: 100%; border-collapse: collapse; border: 1px solid #999; margin: 5px 0;'>")
            changes_html.append("<tr>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 6px; text-align: center; font-weight: bold; font-size: 14px; color: #000;'>DESPLAZAMIENTO</th>")
            changes_html.append("</tr>")
            changes_html.append("</table>")

            # Información del desplazamiento
            changes_html.append(
                "<table style='width: 100%; border-collapse: collapse; border: 1px solid #999; margin: 0; font-size: 13px; color: #000;'>")
            changes_html.append("<tr>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: left; font-weight: bold; font-size: 13px;'>Nombre</th>")
            changes_html.append("</tr>")
            changes_html.append("<tr>")
            changes_html.append(
                f"<td style='border: 1px solid #999; padding: 4px 6px; font-size: 13px; color: #000; font-weight: bold;'>{displacement.destination_id.name} → {displacement.destination_id.name} ({initial_date} - {final_date})</td>")
            changes_html.append("</tr>")
            changes_html.append("</table>")

            # Tabla de cambios - solo mostrar servicios que cambiaron
            changes_found = False
            changes_html.append(
                "<table style='width: 100%; border-collapse: collapse; border: 1px solid #999; margin: 5px 0; font-size: 13px; color: #000;'>")
            changes_html.append("<thead>")
            changes_html.append("<tr>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: left; font-weight: bold; font-size: 13px;'>Servicio</th>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-weight: bold; font-size: 13px;'>Tipo de Cambio</th>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-weight: bold; font-size: 13px;'>Cantidad Anterior</th>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-weight: bold; font_size: 13px;'>Cantidad Nueva</th>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-weight: bold; font-size: 13px;'>Precio Anterior</th>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-weight: bold; font-size: 13px;'>Precio Nuevo</th>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-weight: bold; font-size: 13px;'>Total Anterior</th>")
            changes_html.append(
                "<th style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-weight: bold; font-size: 13px;'>Total Nuevo</th>")
            changes_html.append("</tr>")
            changes_html.append("</thead>")
            changes_html.append("<tbody>")

            # Crear diccionarios para mapear servicios
            original_dict = {service['service_name']: service for service in original_services}
            new_dict = {service['service_name']: service for service in new_services_with_names}
            all_services = set(original_dict.keys()) | set(new_dict.keys())

            for service_name in sorted(all_services):
                original = original_dict.get(
                    service_name, {'quantity': 0, 'unit_price': 0, 'total': 0})
                new = new_dict.get(
                    service_name, {'quantity': 0, 'unit_price': 0, 'total': 0})

                # Determinar tipo de cambio y mostrar solo si hay cambios
                change_type = ""
                show_row = False

                if service_name not in original_dict and service_name in new_dict:
                    change_type = "Nuevo"
                    show_row = True
                elif service_name in original_dict and service_name not in new_dict:
                    change_type = "Eliminado"
                    show_row = True
                elif (service_name in original_dict and service_name in new_dict and
                      (original['quantity'] != new['quantity'] or original['unit_price'] != new['unit_price'])):
                    change_type = "Modificado"
                    show_row = True

                if show_row:
                    changes_found = True
                    changes_html.append("<tr>")
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; font-size: 13px; color: #000;'>{service_name}</td>")
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #000; font-weight: bold;'>{change_type}</td>")

                    # Cantidad
                    qty_original = f"{int(original['quantity'])}" if original['quantity'] > 0 else "-"
                    qty_new = f"{int(new['quantity'])}" if new['quantity'] > 0 else "-"
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #000;'>{qty_original}</td>")
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #000;'>{qty_new}</td>")

                    # Precio unitario
                    price_original = f"$ {original['unit_price']:,.0f}".replace(
                        ',', '.') if original['unit_price'] > 0 else "-"
                    price_new = f"$ {new['unit_price']:,.0f}".replace(
                        ',', '.') if new['unit_price'] > 0 else "-"
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #000;'>{price_original}</td>")
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #000;'>{price_new}</td>")

                    # Total
                    total_original = f"$ {original['total']:,.0f}".replace(
                        ',', '.') if original['total'] > 0 else "-"
                    total_new = f"$ {new['total']:,.0f}".replace(
                        ',', '.') if new['total'] > 0 else "-"
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #000;'>{total_original}</td>")
                    changes_html.append(
                        f"<td style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #000;'>{total_new}</td>")

                    changes_html.append("</tr>")

            # Si no hay cambios, mostrar mensaje
            if not changes_found:
                changes_html.append("<tr>")
                changes_html.append(
                    "<td colspan='8' style='border: 1px solid #999; padding: 4px 6px; text-align: center; font-size: 13px; color: #666; font-style: italic;'>No se encontraron cambios en los servicios</td>")
                changes_html.append("</tr>")

            changes_html.append("</tbody>")
            changes_html.append("</table>")

            # Resumen simple
            original_total = sum(service['total']
                                 for service in original_services)
            new_total = sum(service['total']
                            for service in new_services_with_names)
            difference = new_total - original_total

            changes_html.append(
                "<div style='margin: 5px 0; padding: 5px; border: 1px solid #ccc; font-size: 13px; color: #000;'>")
            changes_html.append("<strong>Resumen:</strong> ")
            changes_html.append(
                f"Total Original: $ {original_total:,.0f}".replace(',', '.'))
            changes_html.append(
                f" → Total Nuevo: $ {new_total:,.0f}".replace(',', '.'))

            if difference != 0:
                sign = "+" if difference > 0 else ""
                color = "#dc3545" if difference > 0 else "#28a745"
                changes_html.append(
                    f" <span style='color: {color};'>({sign}$ {difference:,.0f}".replace(',', '.') + ")</span>")
            else:
                changes_html.append(
                    " <span style='color: #666;'>(Sin cambio en el total)</span>")

            changes_html.append("</div>")
            changes_html.append("</div>")

        changes_html.append("</div>")

        # Publicar en las notas de la solicitud
        html_content = "".join(changes_html)
        self.expense_id.sudo().message_post(
            body=Markup(html_content),
        )
