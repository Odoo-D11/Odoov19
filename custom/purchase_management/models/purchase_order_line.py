
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup


class PurchaseManagementOrderLine(models.Model):
    _name = 'purchase.management.order.line'
    _description = 'Línea de Orden de Compra'

    """MANY2ONE"""
    order_id = fields.Many2one(
        'purchase.management.order', string='Orden de Compra', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'warehouse.product.variant', string='Producto', required=True)
    cost_center_id = fields.Many2one(
        'cost.center', string='Centro de costo', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda',
                                  required=True, compute='_compute_currency_id', store=True)
    """FLOAT"""
    qty = fields.Float(string='Cantidad', required=True, digits=(16, 0))
    """MONETARY"""
    price_unit = fields.Monetary(string='Precio Unit.',
                              required=True, currency_field='currency_id')
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal',
                            store=True, currency_field='currency_id')

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.price_unit

    @api.depends('order_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = line.order_id.currency_id
