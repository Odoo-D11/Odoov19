
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class WarehouseQuant(models.Model):
    _name = "warehouse.quant"
    _description = "Invetario físico"
    _rec_name = "product_id"

    """MANY2ONE"""
    product_id = fields.Many2one(
        'warehouse.product', string="Producto", required=True)
    warehouse_id = fields.Many2one(
        'warehouse.warehouse', string="Almacén", required=True)
    """FLOAT"""
    quantity = fields.Float(
        string="Cantidad", required=True, default=0.0, digits=(12, 0))
