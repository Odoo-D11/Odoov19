
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class WarehousePicking(models.Model):
    _name = "warehouse.picking"
    _description = "Transferencia"
    _rec_name = "picking_type_id"

    """MANY2ONE"""
    picking_type_id = fields.Many2one(
        'warehouse.picking.type', string="Tipo de operación", required=True)
    warehouse_id = fields.Many2one(
        'warehouse.warehouse', string="Almacén", required=True)
    """SELECTION"""
    operation_type = fields.Selection(
        related='picking_type_id.operation_type', string="Tipo de operación", readonly=True)
