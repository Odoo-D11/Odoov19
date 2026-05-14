
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class HrTypeAccount(models.Model):
    _name = 'hr.type.account'
    _description = 'Tipo de cuenta'
    _rec_name = 'name'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Ahorros", "Corriente",]
        missing_names = [
            name for name in required_names if name not in existing_names]

        for name in missing_names:
            self.create({
                "name": name
            })
