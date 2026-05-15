from odoo import models, fields, api


class ExpenseRejectionReason(models.Model):
    _name = 'expense.rejection.reason'
    _description = 'Motivo de rechazo'
    _rec_name = 'name'

    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        existing = self.search([]).mapped('name')
        required = [
            'Duplicado',
            'Información incompleta',
            'Sin presupuesto',
            'Otro',
        ]
        for name in [n for n in required if n not in existing]:
            self.create({'name': name})
