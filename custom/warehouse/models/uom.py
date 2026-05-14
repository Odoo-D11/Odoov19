
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class WarehouseUomCategory(models.Model):
    _name = "warehouse.uom.category"
    _description = "Categoría de Unidad de Medida"
    _rec_name = "name"

    """ONE2MANY"""
    uom_ids = fields.One2many(
        'warehouse.uom', 'category_id', string="Unidades de medida")
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)


class WarehouseUom(models.Model):
    _name = "warehouse.uom"
    _description = "Unidad de Medida"
    _rec_name = "name"

    """ONE2MANY"""
    product_ids = fields.One2many(
        'warehouse.product', 'uom_id', string="Productos")
    """MANY2ONE"""
    category_id = fields.Many2one(
        'warehouse.uom.category', string="Categoría", required=True)
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    symbol = fields.Char(string="Símbolo", required=True)
    display_name = fields.Char(
        string="Nombre para mostrar", compute='_compute_display_name',)

    @api.depends('name', 'symbol')
    def _compute_display_name(self):
        for uom in self:
            if uom.name in ['Unidad', 'Mes(es)']:
                uom.display_name = uom.name
            else:
                uom.display_name = uom.symbol or uom.name

    @api.model
    def init(self):
        Category = self.env['warehouse.uom.category']
        categories = [
            "Unidad",
            "Peso",
            "Horario de trabajo",
            "Longitud / Distancia",
            "Superficie",
            "Volumen",
        ]
        existing_cats = {c.name: c for c in Category.search([])}
        for cat_name in categories:
            if cat_name not in existing_cats:
                existing_cats[cat_name] = Category.create({'name': cat_name})
        uoms = [
            # Unidad
            {"name": "Unidad", "category": "Unidad", "symbol": "ud"},
            {"name": "Viajes", "category": "Unidad", "symbol": "viaje"},
            # {"name": "Docena", "category": "Unidad", "symbol": "doc."},

            # Peso (común en mercados y comercio)
            {"name": "Gramo", "category": "Peso", "symbol": "gr"},
            {"name": "Kilogramo", "category": "Peso", "symbol": "kg"},
            # {"name": "Libra", "category": "Peso", "symbol": "lb"},
            # {"name": "Tonelada", "category": "Peso", "symbol": "t"},

            # Horario de trabajo
            {"name": "Mes(es)", "category": "Horario de trabajo",
             "symbol": "mes"},

            # Longitud / Distancia
            # {"name": "Centímetro", "category": "Longitud / Distancia", "symbol": "cm"},
            {"name": "Metro", "category": "Longitud / Distancia", "symbol": "m"},
            # {"name": "Kilómetro", "category": "Longitud / Distancia", "symbol": "km"},

            # Superficie
            {"name": "Metro cuadrado", "category": "Superficie", "symbol": "m²"},

            # Volumen / Líquidos
            # {"name": "Mililitro", "category": "Volumen", "symbol": "mL"},
            # {"name": "Litro", "category": "Volumen", "symbol": "l"},
            {"name": "Galón", "category": "Volumen", "symbol": "gal"},

        ]
        existing = set(self.search([]).mapped("name"))
        for uom_data in uoms:
            if uom_data["name"] not in existing:
                cat = existing_cats.get(uom_data["category"])
                if cat:
                    self.create({
                        "name": uom_data["name"],
                        "category_id": cat.id,
                        "symbol": uom_data["symbol"],
                    })
