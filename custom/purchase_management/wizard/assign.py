
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class AssignPurchaseResponsibleWizard(models.TransientModel):
    _name = 'assign.purchase.responsible.wizard'
    _description = 'Asignar Responsable de Compras'

    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de Cotización', required=True)
    responsible_id = fields.Many2one(
        'purchase.member', string='Responsable de Compras', required=True,
        domain="[('team_id.name', '=', 'Compras')]"
    )

    def action_assign_responsible(self):
        template = self.env.ref(
            'purchase_management.email_template_request_quotation_assign')
        self.ensure_one()
        self.env['request.quotation'].browse(
            self.request_quotation_id.id).sudo().write({
                'responsible_purchase_id': self.responsible_id.id,
                'state': 'in_shopping',
            })
        msg = Markup(
            f"<span>La persona responsable de gestionar la solicitud de cotización por parte del área de <span style='color: #017e84;'>Compras</span> es <span style='color: #017e84;'>{self.responsible_id.employee_id.name}</span>.</span>"
        )
        self.request_quotation_id.sudo().message_post(
            body=msg
        )
        template.send_mail(
            self.request_quotation_id.id,
            email_values={
                'email_to': self.responsible_id.employee_id.work_email,
                'email_cc': self.request_quotation_id.responsible_purchase_id.employee_id.work_email,
            }
        )
