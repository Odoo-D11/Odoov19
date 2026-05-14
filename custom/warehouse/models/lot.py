
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class WarehouseLotSerial(models.Model):
    _name = "warehouse.lot.serial"
    _description = "Lote/Número de serie"
    _rec_name = "name"

    """MANY2ONE"""
    product_id = fields.Many2one(
        'warehouse.product', string="Producto", required=True)
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    serial_number = fields.Char(string="Número de serie", required=True)