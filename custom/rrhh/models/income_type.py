
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrIncomeType(models.Model):
    _name = 'hr.income.type'
    _description = 'Tipo de ingreso'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True, )

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = [
            "Subsidio de Transporte",
            "Anticipo de Prima Extralegal",
            "Auxilio de Comunicaciones / Movilización",
            "Bono de Disponibilidad",
        ]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})
