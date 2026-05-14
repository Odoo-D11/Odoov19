
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class Warehouse(models.Model):
    _name = "warehouse.warehouse"
    _description = "Almacén"
    _rec_name = "name"

    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    prefix = fields.Char(string="Prefijo", required=True)
