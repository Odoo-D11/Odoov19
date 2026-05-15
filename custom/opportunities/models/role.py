
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import string

class Role(models.Model):
    _name = 'opportunity.role'
    _description = 'Rol'
    _order = 'name asc'
    _rec_name = 'name'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Principal", "Apoyo"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = string.capwords(vals['name'])
        return super(Role, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = string.capwords(vals['name'])
        return super(Role, self).write(vals)
