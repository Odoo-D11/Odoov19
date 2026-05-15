
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils.utils import convert_first_letter_to_uppercase


class Sector(models.Model):
    _name = 'opportunity.sector'
    _description = 'Sector'
    _order = 'name asc'
    _rec_name = 'name'

    """ONE2MANY"""
    category_ids = fields.One2many(
        'opportunity.category', 'sector_id', string='Categoria')
    type_opportunity_ids = fields.One2many(
        'opportunity.type', 'sector_id', string='Tipo de oportunidad')
    lead_ids = fields.One2many(
        'opportunity', 'sector_id', string='Oportunidades')    
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Privado", "Público"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(Sector, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(Sector, self).write(vals)
