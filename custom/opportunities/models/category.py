
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils.utils import convert_first_letter_to_uppercase


class Category(models.Model):
    _name = 'opportunity.category'
    _description = 'Categoría'
    _order = 'name asc'
    _rec_name = 'name'

    """MANY2ONE"""
    sector_id = fields.Many2one(
        'opportunity.sector', string='Sector', required=True)
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    display_name = fields.Char(
        string='Nombre a mostrar', compute='_compute_display_name')

    @api.depends('name', 'sector_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.sector_id.name} / {rec.name}"

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = (domain or []) + ['|', ('name', operator, name),
                                   ('sector_id.name', operator, name)]
        return super(Category, self).name_search(
            name=name, domain=domain, operator=operator, limit=limit)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        public = ["Distrital", "Central", "Regional"]
        private = ["Banca", "Oil and gas", "Telco", "Salud", "Educación",
                   "Manufactura", "Hoteleria y entretenimiento", "Otros"]

        required_names = public + private
        missing_names = [
            name for name in required_names if name not in existing_names]

        # Obtener los sectores "Público" y "Privado"
        sector_public = self.env['opportunity.sector'].search(
            [('name', '=', 'Público')], limit=1)
        sector_private = self.env['opportunity.sector'].search(
            [('name', '=', 'Privado')], limit=1)

        # Crear los registros faltantes con el sector correspondiente
        for name in missing_names:
            if name in public:
                self.create({
                    "name": name,
                    "sector_id": sector_public.id
                })
            elif name in private:
                self.create({
                    "name": name,
                    "sector_id": sector_private.id
                })

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(Category, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(Category, self).write(vals)
