
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from random import randint


class WarehouseProductCategory(models.Model):
    _name = "warehouse.product.category"
    _description = "Categoría de producto"
    _rec_name = "name"

    def _default_color(self):
        return randint(1, 11)

    """ONE2MANY"""
    product_ids = fields.One2many(
        'warehouse.product', 'category_id', string="Productos")
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    prefix = fields.Char(
        string="Prefijo", required=True,)
    display_name = fields.Char(
        string="Nombre para mostrar", compute='_compute_display_name',)
    """INTEGER"""
    color = fields.Integer(string="Color Index", default=_default_color,)

    @api.model
    def init(self):
        types = [
            ('Material Civil', 'MC'),
            ('Material Eléctrico', 'ME'),
            ('Material Tecnológico', 'MT'),
            ('Equipos Eléctricos', 'EE'),
            ('Equipos Tecnológicos', 'ET'),
            ('Software y Licencias', 'SL'),
            ('Papelería, Cafetería y Aseo', 'PCA'),
        ]
        for name, prefix in types:
            if not self.search([('name', '=', name)]):
                self.create({'name': name, 'prefix': prefix})

    @api.depends('name', 'prefix')
    def _compute_display_name(self):
        for category in self:
            if category.prefix:
                category.display_name = f"[{category.prefix}] {category.name}" or category.name
            else:
                category.display_name = category.name

    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            existing = self.search([
                ('name', '=', record.name),
                ('id', '!=', record.id)
            ])
            if existing:
                raise ValidationError(
                    _("No se permite crear más de una categoría con el mismo nombre.")
                )

    @api.constrains('prefix')
    def _check_unique_prefix(self):
        for record in self:
            if record.prefix:
                existing = self.search([
                    ('prefix', '=', record.prefix),
                    ('id', '!=', record.id)
                ])
                if existing:
                    raise ValidationError(
                        _("No se permite crear más de una categoría con el mismo prefijo.")
                    )
