
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase, _show_error_notification


class RejectRequestWizard(models.TransientModel):
    _name = "reject.request.wizard"
    _description = "Asistente de Rechazo de Solicitud"
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        "request.quotation", string="Solicitud de cotización")
    """SELECTION"""
    view = fields.Selection([
        ('normal', 'Normal'),
        ('min_providers_qty', 'Excepción de Cantidad de Proveedores'),
        ('project_leader', 'Líder de Proyecto'),
    ], string="Vista", default='normal', required=True)
    """TEXT"""
    reason = fields.Text(string="Motivo",)

    def action_reject_request(self):
        min = self.env['ir.config_parameter'].sudo().get_param(
            'purchase_management.min_providers_qty', default=3)
        if not self.reason or self.reason.strip() == "":
            return _show_error_notification(self, _('Debe proporcionar un motivo para el rechazo. Por favor, ingrese una justificación y vuelva a intentarlo.'))
        rfq = self.request_quotation_id
        if rfq:
            if self.view == 'min_providers_qty':
                template = self.env.ref(
                    'purchase_management.mail_template_reject_min_providers_qty')
                template.with_context(
                    exception_providers_qty=rfq.min_providers_qty,
                    min_providers_qty=min,
                    reason=convert_first_letter_to_uppercase(
                        self.reason.strip())
                ).send_mail(rfq.id,
                            email_values={
                                'email_to': rfq.responsible_purchase_id.employee_id.work_email if rfq.category == 'project' else rfq.responsible_id.work_email,
                            })
                rfq.sudo().write({
                    'min_providers_qty': int(min),
                    'is_min_providers_approval_pending': False,
                })
                purchase_area_text = '<span style="color: #017e84;">área de Compras</span>' if rfq.category == 'project' else '<span style="color: #017e84;">responsable</span>'
                msg = Markup(
                    f"<span>Se ha rechazado la solicitud para trabajar con una cantidad menor de proveedores a la establecida por la política corporativa. "
                    f"Se ha registrado la siguiente justificación para este rechazo:<span style='color: #017e84;'>\"{convert_first_letter_to_uppercase(self.reason)}\"</span>. "
                    f"A partir de este momento, la solicitud continúa su proceso bajo la política estándar de mínimo <strong>{int(min)} proveedores</strong> antes del envío de correos a los proveedores. "
                    f"Mientras la solicitud se mantenga en esta etapa previa al envío de correos, el {purchase_area_text} podrá generar una nueva solicitud de aprobación para una excepción en la cantidad de proveedores, si lo considera necesario.</span>"
                )
                rfq.sudo().message_post(body=msg)
            elif self.view == 'project_leader' and rfq.category == 'project':
                template = self.env.ref(
                    'purchase_management.mail_template_reject_project_leader')
                template.with_context(
                    reason=convert_first_letter_to_uppercase(
                        self.reason.strip())
                ).send_mail(rfq.id,
                            email_values={
                                'email_to': rfq.responsible_purchase_id.employee_id.work_email,
                            })
                msg = Markup(
                    f"<span>Se ha decidido no validar la decisión del líder de proyecto de rechazar las cotizaciones recibidas. "
                    f"Motivo indicado: <span style='color: #017e84;'>{convert_first_letter_to_uppercase(self.reason.strip())}</span>. Por lo tanto, la solicitud continuará su proceso de manera normal.</span>"
                )
                rfq.sudo().message_post(body=msg)
                rfq.sudo().write({
                    'state': 'pending_purchase_approval',
                    'rejected_by_project_leader': False,
                })
                rfq.quotation_line_ids.filtered(
                    lambda q: q.rejected).sudo().write({'rejected': False})
            elif self.view == 'normal':
                template = self.env.ref(
                    'purchase_management.mail_template_reject_request_committee_approval')
                template.with_context(
                    reason=convert_first_letter_to_uppercase(
                        self.reason.strip())
                ).send_mail(rfq.id,
                            email_values={
                                'email_to': rfq.responsible_purchase_id.employee_id.work_email if rfq.category == 'project' else rfq.responsible_id.work_email,
                            })
                supplier_names = ', '.join(
                    rfq.quotation_line_ids.mapped('supplier_name'))
                msg = Markup(
                    f"<span>"
                    f"El <span style='color: #017e84;'>comité de compras</span> ha decidido rechazar todas las cotizaciones vinculadas a esta solicitud, "
                    f"correspondientes a los siguientes proveedores: <span style='color: #017e84;'>{supplier_names}</span>, "
                    f"la razón indicada es: <span style='color: #017e84;'>{convert_first_letter_to_uppercase(self.reason.strip())}</span>, "
                    f"por lo tanto, la solicitud será revertida al estado inicial para reiniciar el proceso desde cero y permitir el trabajo con nuevos proveedores."
                    f"</span>"

                )
                rfq.sudo().message_post(body=msg)
                quotations = rfq.quotation_line_ids
                if quotations:
                    quotations.sudo().unlink()

                rfq.sudo().write({
                    'commitee_approval_rejected': True,
                    'state': 'in_shopping',
                    'min_providers_qty': self.env['ir.config_parameter'].sudo().get_param('purchase_management.default_min_providers_qty', default=3),
                })
                rfq.product_line_ids.filtered(
                    lambda s: s.sent_to_emails).sudo().write({'sent_to_emails': False})
                channel = f"quotation_rejection_{rfq.id}"
                self.env['bus.bus']._sendone(
                    channel,
                    "quotation.chart/rejected",
                    {
                        "id": rfq.id,
                        "message": _("La solicitud ha sido rechazada por el comité. Redirigiendo...")
                    }
                )
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'request.quotation',
                    'res_id': rfq.id,
                    'view_mode': 'form',
                    'views': [[False, 'form']],
                    'target': 'main',
                    'context': {'clear_breadcrumbs': True}
                }

        else:
            return _show_error_notification(self, _('La solicitud no se encuentra en un estado válido para ser rechazada. Por favor, verifique e intente nuevamente.'))
