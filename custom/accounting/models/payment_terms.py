
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class AccountingPaymentTerm(models.Model):
    _name = 'accounting.payment.term'
    _description = 'Término de pago'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia',)

    @api.model
    def init(self):
        categories = [
            "Pago Inmediato",
            "30 días",
            "60 días",
            "90 días",
        ]
        existing = set(self.search([]).mapped("name"))
        for name in categories:
            if name not in existing:
                self.create({"name": name})
