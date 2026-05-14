
from odoo import fields, models


class PurchaseConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    """MANY2ONE"""
    approval_min_providers_user_id = fields.Many2one(
        'res.users',
        string="Responsable de aprobación",
        help="Usuario responsable de revisar y aprobar solicitudes de excepción para trabajar con menos proveedores.",
        config_parameter='purchase_management.approval_min_providers_user_id',
    )
    """INTEGER"""
    min_providers_qty = fields.Integer(
        string="Número mínimo de proveedores",
        config_parameter='purchase_management.min_providers_qty',
        default=3,
        help="Número mínimo de proveedores según política corporativa."
    )
