
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class WarehousePickingType(models.Model):
    _name = "warehouse.picking.type"
    _description = "Tipo de operación"
    _rec_name = "name"

    """MANY2ONE"""
    warehouse_id = fields.Many2one('warehouse.warehouse', string="Almacén", required=True)
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    prefix = fields.Char(string="Prefijo", required=True)
    """SELECTION"""
    operation_type = fields.Selection([
        ('incoming', 'Recepción'),
        ('outgoing', 'Entrega'),
        ('internal', 'Transferencia interna'),
    ], string="Tipo de operación", required=True)
