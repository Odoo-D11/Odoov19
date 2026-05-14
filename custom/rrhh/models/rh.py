
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class RhRh(models.Model):
    _name = 'rh.rh'
    _description = 'Grupo sanguíneo'
    _rec_name = 'name'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True,
                       copy=False, index=True, )

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = [
            "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"
        ]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})
