from odoo import fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase, _show_error_notification


class ReturnToRequesterWizard(models.TransientModel):
    _name = 'return.to.requester.wizard'
    _description = 'Devolver SDC al Solicitante'
    _transient_max_count = 100
    _transient_max_hours = 24

    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de Cotización', required=True, readonly=True)
    reason = fields.Text(string='Motivo de devolución', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            return _show_error_notification(
                self, _('Debe ingresar el motivo de la devolución antes de continuar.'))
        rfq = self.request_quotation_id
        reason = convert_first_letter_to_uppercase(self.reason.strip())
        template = self.env.ref(
            'purchase_management.mail_template_return_to_requester')
        template.with_context(return_reason=reason).send_mail(
            rfq.id,
            email_values={
                'email_to': rfq.responsible_id.work_email,
                'email_cc': rfq.responsible_purchase_id.employee_id.work_email if rfq.responsible_purchase_id else '',
            }
        )
        rfq.sudo().write({'state': 'returned'})
        msg = Markup(
            f"<span>La solicitud fue <span style='color: #e67e22;'>devuelta</span> al solicitante "
            f"<span style='color: #017e84;'>{rfq.responsible_id.name}</span>. "
            f"Motivo: <span style='color: #017e84;'>{reason}</span>.</span>"
        )
        rfq.sudo().message_post(body=msg)
