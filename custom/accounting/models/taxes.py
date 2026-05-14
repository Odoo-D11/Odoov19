
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AccountingTax(models.Model):
    _name = 'accounting.tax'
    _description = 'Impuestos'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        categories = [
            "19%",
            "5%",
        ]
        existing = set(self.search([]).mapped("name"))
        for name in categories:
            if name not in existing:
                self.create({"name": name})
