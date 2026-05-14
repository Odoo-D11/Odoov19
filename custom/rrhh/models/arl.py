
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class HrArl(models.Model):
    _name = 'hr.arl'
    _description = 'ARL'
    _rec_name = 'name'

    """ONE2MANY"""
    employee_ids = fields.One2many(
        'hr.employee', 'arl_id', string='Empleados')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Sura", "Positiva", "AXA Colpatria",
                          "Colmena", "Bolívar", "Equidad", "Liberty", "Aurora"]

        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})
