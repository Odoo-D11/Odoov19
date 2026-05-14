
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
from ..utils.utils import (
    format_html_to_sentence_case,
)


class CancelRequestQuotationWizard(models.TransientModel):
    _name = "cancel.request.quotation.wizard"
    _description = "Asistente de Cancelación de la Solicitud"
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        "request.quotation", string="Solicitud de cotización")
    """TEXT"""
    reason = fields.Text(string="Motivo", )

    def action_cancel_request_quotation(self):
        rfq = self.request_quotation_id
        if not rfq:
            raise UserError(_("No se encontró la solicitud asociada."))
        if not self.reason or self.reason.strip() == "":
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe proporcionar un motivo para la cancelación. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        rfq.sudo().write(
            {'state': 'cancelled', 'is_min_providers_approval_pending': False})
        rfq.sudo().message_post(
            body=Markup(
                f"<span>La <span style='color: #017e84;'>solicitud de cotización</span> ha sido <span style='color: #017e84;'>cancelada</span> por el siguiente motivo: </span><span style='color #017e84;'>{format_html_to_sentence_case(self.reason)}</span>"
            ))
