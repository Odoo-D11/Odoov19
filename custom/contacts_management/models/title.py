
from odoo import models, fields, api, _

class ResPartnerTitle(models.Model):
    _name = 'res.partner.title'
    _description = 'Titulo'


    """CHAR"""
    name = fields.Char(string='Titulo', required=True)


    @api.model
    def init(self):
        existing_names = self.search([]).mapped("name")
        required_names = [
            "Sr.",
            "Sra.",
        ]
        missing_names = [
            name for name in required_names if name not in existing_names]

        for name in missing_names:
            self.create({
                "name": name
            })