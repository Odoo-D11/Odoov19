from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase, _show_error_notification


class PurchaseSendMailWizard(models.TransientModel):
    _name = 'purchase.send.mail.wizard'
    _description = 'Wizard para enviar correos electrónicos y completar campos adicionales en solicitudes de cotización'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2MANY"""
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Adjuntos', readonly=True)
    selected_product_line_ids = fields.Many2many(
        'request.product.quotation.line', string='Productos Seleccionados',
        help='Productos seleccionados para enviar a proveedores')
    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de Cotización', readonly=True)
    destination_id = fields.Many2one(
        'res.city', string='Ciudad destino',)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', readonly=True, default=lambda self: self.env.company.currency_id)
    """SELECTION"""
    type = fields.Selection([
        ('rfq_to_purchase', 'Enviar solicitud de cotización a Compras'),
        ('rfq_to_supplier', 'Enviar solicitud de cotización al proveedor'),
        ('rfq_to_project_manager',
         'Enviar solicitud de cotización al Gerente de Proyecto'),
        ('op', 'Enviar Orden de Compra al proveedor')
    ], string='Tipo de correo', required=True, readonly=True,)
    location_delivery = fields.Selection([
        ('warehouse', 'Bodega'),
        ('field', 'Campo')
    ], string='Ubicación')
    """CHAR"""
    supplier_emails = fields.Char(
        string='Para',
        help='Correos separados por coma. Ej: proveedor@mail.com, otro@mail.com'
    )
    subject = fields.Char(string='Asunto', required=True)
    """HTML"""
    body = fields.Html(string='Cuerpo', )
    """INTEGER"""
    min_providers_qty = fields.Integer(string='Nro. mínimo de proveedores',
                                       readonly=True, help='Indica el número mínimo de proveedores con los que se debe trabajar en la solicitud de cotización, según la política corporativa.')
    exception_providers_qty = fields.Integer(string='Nro. de Proveedores en Excepción',
                                             help='Número de proveedores que se manejarán en esta solicitud de cotización bajo una excepción a la política corporativa.')
    justification = fields.Text(string='Justificación')
    price = fields.Monetary(string='Precio estimado',
                            currency_field='currency_id',)
    """BOOLEAN"""
    instructions = fields.Boolean(
        'Instrucciones', default=False, readonly=True)
    complete_fields = fields.Boolean(
        'Completar campos', default=False, readonly=True)
    bugeted = fields.Boolean(
        string='Esta dentro del presupuesto?', default=False)
    show_provider_instructions = fields.Boolean(
        string='Mostrar instrucciones de proveedores', readonly=True,
        help='Si está activado, se mostrarán las instrucciones previas al envío de solicitudes de cotización a proveedores.'
    )
    edit_request_quotation = fields.Boolean(
        string='Editar solicitud de cotización', readonly=True,)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        is_supplier_type = (
            res.get('type') == 'rfq_to_supplier'
            or self.env.context.get('default_type') == 'rfq_to_supplier'
        )
        if is_supplier_type:
            rfq_id = res.get('request_quotation_id') or self.env.context.get(
                'default_request_quotation_id')
            if rfq_id:
                rfq = self.env['request.quotation'].browse(rfq_id)
                tech_att_ids = rfq.technical_spec_attachment_ids.ids
                current_ids = []
                for cmd in res.get('attachment_ids', []):
                    if isinstance(cmd, (list, tuple)) and cmd[0] == 6:
                        current_ids = list(cmd[2])
                        break
                merged = list(set(current_ids + tech_att_ids))
                if merged:
                    res['attachment_ids'] = [[6, 0, merged]]
        return res

    def action_next(self):
        self.ensure_one()
        if self.request_quotation_id:
            if self.type == 'rfq_to_purchase':
                self.instructions = not self.instructions
                self.complete_fields = not self.complete_fields
            elif self.type == 'rfq_to_supplier':
                self.show_provider_instructions = not self.show_provider_instructions
                return {
                    'type': 'ir.actions.client',
                    'tag': 'purchase_management_product_selector',
                    'params': {'request_quotation_id': self.request_quotation_id.id},
                    'name': self.request_quotation_id.reference,
                }
        else:
            return _show_error_notification(self, _('No se ha encontrado la solicitud asociada. Por favor, comuníquese con el administrador del sistema.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.send.mail.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_edit_request_quotation(self):
        self.ensure_one()
        self.show_provider_instructions = not self.show_provider_instructions
        if self.show_provider_instructions:
            self.edit_request_quotation = False
        else:
            self.edit_request_quotation = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.send.mail.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_view_mail_preview(self):
        self.ensure_one()
        if not self.location_delivery:
            return _show_error_notification(self, _('Debe seleccionar la ubicación de entrega (Bodega o Campo) para continuar.'))
        if self.bugeted and self.price <= 0:
            return _show_error_notification(self, _('Si la solicitud está dentro del presupuesto, debe ingresar un precio estimado mayor a 0 para continuar.'))
        self.complete_fields = not self.complete_fields
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.send.mail.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _check_exception_providers_qty(self):
        responsable_approval_user = self.env['ir.config_parameter'].sudo().get_param(
            'purchase_management.approval_min_providers_user_id', default=False)
        rfq = self.request_quotation_id
        if self.edit_request_quotation:
            template = self.env.ref(
                'purchase_management.mail_template_notify_min_providers_qty')
            # Evitar enviar una excepción duplicada si ya hay una pendiente de aprobación
            if rfq.is_min_providers_approval_pending:
                return _show_error_notification(self, _('Ya existe una solicitud de excepción pendiente de aprobación para esta solicitud. Por favor, espere a que sea procesada antes de enviar una nueva.'))
            if self.exception_providers_qty <= 0 or self.exception_providers_qty > self.min_providers_qty:
                return _show_error_notification(self, _('El número de proveedores en excepción debe ser mayor a 0 y menor o igual al número mínimo de proveedores establecido (%s). Por favor, verifique e intente nuevamente.') % self.min_providers_qty)
            if not self.justification or self.justification.strip() == "":
                return _show_error_notification(self, _('Debe proporcionar una justificación válida para el número de proveedores seleccionado. Por favor, verifique e intente nuevamente.'))
            if not responsable_approval_user:
                return _show_error_notification(self, _('No se ha definido un responsable para este tipo de excepción. Por favor, comuníquese con el administrador del sistema.'))
            template.with_context(
                min_providers_qty=self.min_providers_qty,
                exception_providers_qty=self.exception_providers_qty,
                exception_reason=convert_first_letter_to_uppercase(
                    self.justification.strip()),
                responsible_purchase_id=rfq.responsible_purchase_id.employee_id.name,
            ).send_mail(
                rfq.id,
                email_values={
                    'email_to': self.env['res.users'].search([
                        ('id', '=', int(responsable_approval_user))], limit=1).employee_id.work_email,
                    'email_cc': rfq.responsible_purchase_id.employee_id.work_email if (rfq.category == 'project' or rfq.responsible_purchase_id) else rfq.responsible_id.work_email,
                }
            )
            rfq.sudo().write({
                'min_providers_qty': self.exception_providers_qty,
                'is_min_providers_approval_pending': True,
                'commitee_approval_rejected': False,
            })
            msg = Markup(
                f"<span>Se ha enviado una solicitud para trabajar con <span style='color: #017e84;'>{self.exception_providers_qty} {'proveedor' if self.exception_providers_qty == 1 else 'proveedores'}</span> en lugar del mínimo de <span style='color: #017e84;'>{self.min_providers_qty} proveedores</span>. Justificación: <span style='color: #017e84;'>\"{convert_first_letter_to_uppercase(self.justification.strip())}\"</span>. Mientras esta solicitud esté pendiente de aprobación, no podrá continuar con la gestión.</span>")
        else:
            raw_emails = self.supplier_emails or ''
            new_emails = set(e.strip()
                             for e in raw_emails.split(',') if e.strip())
            if not new_emails:
                return _show_error_notification(self, _('Debe ingresar al menos un correo electrónico para enviar la solicitud de cotización.'))
            template = self.env.ref(
                'purchase_management.mail_template_send_rfq')
            attachment_ids = [(4, att.id) for att in self.attachment_ids]
            for email in new_emails:
                template.send_mail(
                    rfq.id,
                    email_values={
                        'email_to': email,
                        'email_cc': rfq.responsible_purchase_id.employee_id.work_email if (rfq.category == 'project' or rfq.responsible_purchase_id) else rfq.responsible_id.work_email,
                        'subject': self.subject,
                        'body_html': self.body,
                        'attachment_ids': attachment_ids,
                    }
                )
            # Actualiza sent_to_emails en las líneas de productos seleccionadas
            for line in self.selected_product_line_ids:
                current = set(e.strip() for e in (
                    line.sent_to_emails or '').split(',') if e.strip())
                merged = current | new_emails
                line.sudo().write(
                    {'sent_to_emails': ', '.join(sorted(merged))})
            # Genera el mensaje para el chatter
            email_list = ', '.join(sorted(new_emails))
            selected = len(self.selected_product_line_ids)
            total = len(rfq.product_line_ids.filtered(
                lambda l: not l.display_type))
            msg = Markup(
                "<span>Se %s enviado <span style='color: #017e84;'>%s/%s solicitados</span> "
                "al siguiente correo: <span style='color: #017e84;'>%s</span>.</span>"
            ) % ("han" if selected != 1 else "ha", selected, total, email_list)
            rfq.sudo().write({
                'state': 'sent',
                'all_quotation_rejected': False,
                'commitee_approval_rejected': False,
            })
        rfq.sudo().message_post(
            body=msg
        )
        return True

    def send_mail(self):
        self.ensure_one()
        rfq = self.request_quotation_id
        if rfq:
            if rfq.category == 'project':
                if self.type == 'rfq_to_purchase':
                    template = self.env.ref(
                        'purchase_management.mail_template_rfq_to_purchase')
                    responsible_purchase_id = self.env['assigned.project'].search(
                        [('project_id', '=', rfq.project_id.id)], limit=1).mapped('member_id')
                    if not responsible_purchase_id:
                        return _show_error_notification(self, _('No se ha asignado un responsable en el área de Compras para este proyecto. Por favor, comuníquese con el administrador del sistema.'))
                    rfq.sudo().write({
                        'state': 'in_shopping',
                        'reference': 'SDC/' + str(rfq.project_id.prefix) + self.env['ir.sequence'].next_by_code('request.quotation') or 'New',
                        'responsible_purchase_id': responsible_purchase_id.id,
                    })
                    self.env['purchase.additional.information'].sudo().create({
                        'request_quotation_id': rfq.id,
                        'location_delivery': self.location_delivery,
                        'destination_id': self.destination_id.id if self.destination_id else False,
                        'suggested_supplier_ids': self.supplier_emails or False,
                        'bugeted': self.bugeted,
                        'estimated_price': self.price,
                    })
                    template.send_mail(
                        rfq.id,
                        email_values={
                            'email_to': responsible_purchase_id.employee_id.work_email,
                            'email_cc': rfq.responsible_id.work_email,
                            'subject': self.subject + f" - {rfq.reference}",
                            'body_html': self.body,
                        }
                    )
                    msg = Markup(
                        f"<span>La solicitud de cotización ha sido enviada a "
                        f"<span style='color: #017e84;'>{responsible_purchase_id.employee_id.name}</span> "
                        f"del área de <span style='color: #017e84;'>Compras</span>, quien será la persona responsable de su gestión.</span>"
                    )

                    rfq.sudo().message_post(
                        body=msg
                    )
                if self.type == 'rfq_to_supplier':
                    if rfq.state not in ['in_shopping', 'sent']:
                        return _show_error_notification(self, _('La solicitud de cotización debe estar en estado "En Compras" o "Enviado" para ser enviada a los proveedores. Por favor, verifique e intente nuevamente.'))
                    return self._check_exception_providers_qty()
                if self.type == 'rfq_to_project_manager':
                    template = self.env.ref(
                        'purchase_management.mail_template_rfq_to_project_leader')
                    project_manager_email = rfq.responsible_id.work_email
                    if not project_manager_email:
                        raise UserError(
                            _('El gerente de proyecto no tiene un correo electrónico asignado. Por favor, comuníquese con el administrador del sistema.'))
                    template.send_mail(
                        rfq.id,
                        email_values={
                            'email_to': project_manager_email,
                            'email_cc': rfq.responsible_purchase_id.employee_id.work_email,
                            'subject': self.subject,
                            'body_html': self.body,
                        }
                    )
                    rfq.sudo().write({
                        'state': 'pending_project_approval',
                    })
                    msg = Markup(
                        f"<span>Las cotizaciones para la <span style='color: #017e84;'>solicitud</span> han sido creadas y <span style='color: #017e84;'>enviadas</span> al <span style='color: #017e84;'>Líder de Proyecto</span> para su aprobación.</span>"
                    )
                    rfq.sudo().message_post(
                        body=msg
                    )
            elif rfq.category == 'admin':
                if self.type == 'rfq_to_purchase':
                    responsible_purchase_id = self.env['assigned.project'].search(
                        [('project_id', '=', rfq.project_id.id)], limit=1).mapped('member_id')
                    if not responsible_purchase_id:
                        return _show_error_notification(self, _('No se ha asignado un responsable en el área de Compras para este proyecto. Por favor, comuníquese con el administrador del sistema.'))
                    rfq.sudo().write({
                        'state': 'in_shopping',
                        'responsible_purchase_id': responsible_purchase_id.id,
                    })
                    self.env['purchase.additional.information'].sudo().create({
                        'request_quotation_id': rfq.id,
                        'location_delivery': self.location_delivery,
                        'destination_id': self.destination_id.id if self.destination_id else False,
                        'suggested_supplier_ids': self.supplier_emails or False,
                        'bugeted': self.bugeted,
                        'estimated_price': self.price,
                    })
                    template = self.env.ref('purchase_management.mail_template_rfq_to_purchase')
                    template.send_mail(
                        rfq.id,
                        email_values={
                            'email_to': responsible_purchase_id.employee_id.work_email,
                            'email_cc': rfq.responsible_id.work_email,
                            'subject': self.subject + f" - {rfq.reference}",
                            'body_html': self.body,
                        }
                    )
                    msg = Markup(
                        f"<span>La solicitud de cotización ha sido enviada a "
                        f"<span style='color: #017e84;'>{responsible_purchase_id.employee_id.name}</span> "
                        f"del área de <span style='color: #017e84;'>Compras</span>, quien será la persona responsable de su gestión.</span>"
                    )
                    rfq.sudo().message_post(body=msg)
                else:
                    return self._check_exception_providers_qty()
        else:
            return _show_error_notification(self, _('No se ha encontrado la solicitud asociada. Por favor, comuníquese con el administrador del sistema.'))
