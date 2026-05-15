
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import string


class Enterpise(models.Model):
    _name = 'opportunity.enterprise'
    _description = 'Empresa'
    _order = 'name asc'
    _rec_name = 'name'

    """ONE2MANY"""
    lead_ids = fields.One2many(
        'opportunity', 'enterprise_id', string='Oportunidades')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Tsg The It Experts",
                          "Kreivo", "Knox", "Novacom Net"]
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
        return super(Enterpise, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = string.capwords(vals['name'])
        return super(Enterpise, self).write(vals)
