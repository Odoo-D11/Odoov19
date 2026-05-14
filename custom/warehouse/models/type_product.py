from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class TypeProduct(models.Model):
    _name = "type.product"
    _description = "Tipo de producto"
    _rec_name = "name"

    """ONE2MANY"""
    product_ids = fields.One2many(
        'warehouse.product', 'type_product_id', string="Productos")

    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    display_name = fields.Char(
        string='Nombre para mostrar', compute='_compute_display_name')

    @api.depends('name')
    def _compute_display_name(self):
        for record in self:
            if record.name == "Producto":
                record.display_name = "[PROD] Productos (Bienes físicos, Ej. Tecnología, Portátiles, Firewall, UPS)"
            elif record.name == "Servicio":
                record.display_name = "[SERV] Servicios (Consultoría, mantenimiento, etc.)"
            elif record.name == "Consumible":
                record.display_name = "[CONS] Consumibles (Artículos de uso frecuente, Ej. Café, Papelería, Toner)"
            else:
                record.display_name = record.name

    @api.model
    def init(self):
        types = [
            "Producto",
            "Servicio",
            "Consumible",
        ]
        existing = set(self.search([]).mapped("name"))
        for name in types:
            if name not in existing:
                self.create({"name": name})
