
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from ..utils.utils import (
    is_html_content_empty,
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
    _normalize_name,
)
import unicodedata
from collections import defaultdict


class WarehouseProductVariant(models.Model):
    _name = "warehouse.product.variant"
    _description = "Variante del producto"
    _rec_name = "display_name"

    _sql_constraints = [
        ('unique_name_per_product', 'unique(product_id, name)',
         'Ya existe una variante con ese nombre para este producto.'),
    ]

    """MANY2ONE"""
    product_id = fields.Many2one(
        'warehouse.product', string="Producto", required=True, ondelete='cascade')
    currency_id = fields.Many2one(
        'res.currency', string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id.id,
        domain="[('name', '=', 'COP')]"
    )
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    sku = fields.Char(string="Referencia Interna",)
    barcode = fields.Char(string="Código de barras",)
    display_name = fields.Char(
        string="Nombre para mostrar", compute="_compute_display_name",)
    """MONETARY"""
    estimated_price = fields.Monetary(string="Precio estimado", digits=(16, 0),
                                      required=True, currency_field='currency_id')
    """SELECTION"""
    tracked = fields.Selection([
        ('none', 'Sin seguimiento'),
        ('lot/serial', 'Por lote/Nro. de serie'),
    ], string="Trazabilidad", default='none', required=True)
    """ONE2MANY"""
    alias_ids = fields.One2many(
        'warehouse.variant.alias', 'variant_id', string='También conocida como...')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals and vals['name']:
                vals['name'] = _normalize_name(vals['name'])
        records = super(WarehouseProductVariant, self).create(vals_list)
        product_records = defaultdict(list)
        for record in records:
            product_records[record.product_id.id].append(record)
        for product_id, variant_records in product_records.items():
            product = variant_records[0].product_id
            existing_count = self.search_count([
                ('product_id', '=', product_id),
                ('id', 'not in', [r.id for r in variant_records])
            ])
            for i, record in enumerate(variant_records):
                seq = existing_count + i + 1
                if product.sku:
                    record.sku = f"{product.sku}-{record.id}"
                if product.barcode:
                    record.barcode = product.barcode[:-1] + str(seq)
        return records

    def write(self, vals):
        if 'name' in vals and vals['name']:
            vals['name'] = _normalize_name(vals['name'])
        return super(WarehouseProductVariant, self).write(vals)

    @api.depends('name', 'sku')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.product_id.name} {record.name}"

    @api.constrains('estimated_price')
    def _check_estimated_price(self):
        for record in self:
            if record.estimated_price <= 0:
                raise ValidationError(
                    _("El precio estimado debe ser mayor a cero. Por favor, verifique el valor ingresado para la variante '%s'.") % record.display_name)

    def action_open_aliases(self):
        """Abre el formulario de la variante con el panel de alias en un popup."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'warehouse.product.variant',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('warehouse.view_warehouse_product_variant_form').id,
            'target': 'new',
        }

    @api.constrains('name')
    def _check_name_not_empty(self):
        for record in self:
            if not record.name.strip():
                raise ValidationError(
                    _("El nombre de la variante no puede estar vacío o contener solo espacios. Por favor, ingrese un nombre válido para la variante del producto '%s'.") % record.product_id.name)
