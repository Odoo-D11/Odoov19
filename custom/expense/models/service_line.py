
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseServiceLine(models.Model):
    _name = 'expense.service.line'
    _description = 'Línea de servicio'
    _rec_name = 'service_id'

    """MANY2ONE"""
    displacement_id = fields.Many2one(
        'expense.displacement', string='Desplazamiento', required=True, ondelete='cascade')
    service_id = fields.Many2one(
        'expense.service', string='Servicio', required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id.id)
    """FLOAT"""
    quantity = fields.Float(
        string='Cantidad', required=True, digits=(12, 0), default=1)
    """MONETARY"""
    unit_price = fields.Monetary(string='Precio Unitario', currency_field='currency_id',
                                 required=True, )
    total_amount = fields.Monetary(
        currency_field='currency_id', string='Total', compute='_compute_total_amount', store=True, )

    @api.depends('quantity', 'unit_price')
    def _compute_total_amount(self):
        for line in self:
            line.total_amount = line.quantity * line.unit_price

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('displacement_id')._notify_timeline_update(
            reason="service_line_create"
        )
        return records

    def write(self, vals):
        affected_displacements = self.mapped('displacement_id')
        res = super().write(vals)
        if res:
            (affected_displacements | self.mapped('displacement_id'))._notify_timeline_update(
                reason="service_line_write"
            )
        return res

    def unlink(self):
        affected_displacements = self.mapped('displacement_id')
        res = super().unlink()
        if res:
            affected_displacements._notify_timeline_update(
                reason="service_line_unlink"
            )
        return res
