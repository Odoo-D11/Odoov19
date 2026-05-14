# -*- coding: utf-8 -*-

import unicodedata
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from ..utils.utils import (
    _normalize_name,
)


class WarehouseVariantAlias(models.Model):
    _name = 'warehouse.variant.alias'
    _description = 'Alias de variante de producto'
    _rec_name = 'name'
    _order = 'name'

    _sql_constraints = [
        ('unique_alias_per_variant', 'UNIQUE(name, variant_id)',
         'Este alias ya existe para esta variante.'),
    ]

    name = fields.Char(
        string='Alias', required=True,
        help='Nombre alternativo con el que los usuarios suelen solicitar esta variante.')
    variant_id = fields.Many2one(
        'warehouse.product.variant', string='Variante',
        required=True, ondelete='cascade', index=True)

    # Campos relacionados de solo lectura (útiles en listas)
    product_name = fields.Char(
        related='variant_id.product_id.name', string='Producto', store=True, readonly=True)
    variant_name = fields.Char(
        related='variant_id.name', string='Variante', store=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = _normalize_name(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = _normalize_name(vals['name'])
        return super().write(vals)

    @api.constrains('name')
    def _check_name_not_empty(self):
        for record in self:
            if not record.name or not record.name.strip():
                raise ValidationError(_('El alias no puede estar vacío.'))
