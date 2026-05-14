
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from ..utils.utils import convert_first_letter_to_uppercase


class ProjectCategory(models.Model):
    _name = "project.category"
    _description = "Categoría de Proyecto"

    """ONE2MANY"""
    project_ids = fields.One2many(
        "project.management", "category_id", string="Proyectos")
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)

    @api.model
    def init(self):
        categories = [
            "Administrativo",
            "Proyecto",
        ]
        existing = set(self.search([]).mapped("name"))
        for name in categories:
            if name not in existing:
                self.create({"name": name})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals:
                vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(ProjectCategory, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(ProjectCategory, self).write(vals)
