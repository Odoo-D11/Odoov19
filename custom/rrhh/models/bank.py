
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class InheritResBank(models.Model):
    _inherit = 'res.bank'

    """ONE2MANY"""
    employee_ids = fields.One2many(
        'hr.employee', 'bank_id', string='Empleados')

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Bancolombia", "Banco Av. Villas", "Banco Caja Social",
                          "Davivienda", "Lulo Bank", "Banco de Bogotá", "BBVA",
                          "Banco del Occidente", "Scotiabank Colpatria", "Itau", "Nu Colombia",
                          "Nequi"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        for name in missing_names:
            self.create({
                "name": name
            })
