
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseEnterprise(models.Model):
    _name = 'expense.enterprise'
    _description = 'Empresa'
    _rec_name = 'name'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    prefix = fields.Char(string='Prefijo', required=True)

    @api.model
    def init(self):
        existing = self.search([]).mapped('name')
        required = [
            ('Consorcio Llano Seguro 2024', 'LLA'),
            ('Knox It Sas', 'KNO'),
            ('It Business Talent Sas', 'ITB'),
            ('Kreivo', 'KRE'),
            ('Novacom Net Sas', 'NOV'),
            ('Tsg The It Experts Sas', 'TSG'),
            ('UT Alcaldia Bogota 2024', 'UTA'),
            ('UT SCB 2024 Buenaventura', 'SCB'),
            ('UT SCJ 2024 Jamundi', 'SCJ'),
            ('UT Tecnologias Integradas 2023', 'UTT'),
        ]
        for name, prefix in [item for item in required if item[0] not in existing]:
            self.create({'name': name, 'prefix': prefix})
