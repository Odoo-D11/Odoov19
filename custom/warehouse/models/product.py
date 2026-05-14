
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from ..utils.utils import (
    is_html_content_empty,
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
    _normalize_name,
)
import unicodedata
from datetime import datetime, timedelta


class WarehouseProduct(models.Model):
    _name = "warehouse.product"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Producto"
    _rec_name = "name"

    """ONE2MANY"""
    variant_ids = fields.One2many(
        'warehouse.product.variant', 'product_id', string="Variantes del producto")
    """MANY2ONE"""
    category_id = fields.Many2one(
        'warehouse.product.category', string="Categoría", required=True)
    uom_id = fields.Many2one(
        'warehouse.uom', string="Unidad de medida", )
    type_product_id = fields.Many2one(
        'type.product', string="Tipo de producto", required=True)
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    sku = fields.Char(string="Referencia Interna",)
    barcode = fields.Char(string="Código de barras",)
    """TEXT"""
    description = fields.Text(string="Descripción", required=True)

    @api.model
    def get_variant_popup_view_id(self):
        view = self.env.ref(
            'warehouse.view_warehouse_product_variant_popup', raise_if_not_found=False)
        return view.id if view else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals and vals['name']:
                vals['name'] = _normalize_name(vals['name'])
        res = super(WarehouseProduct, self).create(vals_list)
        for record in res:
            year_suffix = str(datetime.now().year)[-2:]
            record.sku = f"{record.name[:4].upper()}-{year_suffix}{record.id}-{record.category_id.prefix.upper()}"
            record.barcode = f"7704724{year_suffix}{record.id}0"
        return res

    def write(self, vals):
        if 'name' in vals and vals['name']:
            vals['name'] = _normalize_name(vals['name'])
        return super(WarehouseProduct, self).write(vals)

    @api.onchange('description')
    def _onchange_description(self):
        for record in self:
            if record.description:
                record.description = format_html_to_sentence_case(
                    record.description)

    @api.constrains('description')
    def _check_description_not_empty(self):
        for record in self:
            if is_html_content_empty(record.description):
                raise ValidationError(
                    _("La descripción no puede estar vacía. Por favor, verifique e intente de nuevo."))
            if len(''.join(c for c in format_html_to_sentence_case(record.description) if c.isalnum())) > 200:

                raise ValidationError(
                    _("La descripción no puede contener más de 200 caracteres (sin contar espacios ni caracteres especiales). Por favor, verifique e intente de nuevo."))

    @api.constrains('name')
    def _check_name_not_empty(self):
        for record in self:
            if not record.name.strip():
                raise ValidationError(
                    _("El nombre no puede estar vacío. Por favor, verifique e intente de nuevo."))
            if len(record.name.replace(" ", "")) > 25:
                raise ValidationError(
                    _("El nombre no puede contener más de 25 caracteres (sin contar espacios). Por favor, verifique e intente de nuevo."))

    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            if not record.name:
                continue
            duplicate = self.env['warehouse.product'].search([
                ('name', 'ilike', record.name.strip()),
                ('id', '!=', record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("Ya existe un producto con un nombre igual o similar: '%s'. "
                      "Por favor, verifique e ingrese un nombre único.")
                    % duplicate.name
                )

    @api.constrains('barcode')
    def _check_unique_barcode(self):
        for record in self:
            if not record.barcode or not record.barcode.strip():
                continue
            duplicate = self.env['warehouse.product'].search([
                ('barcode', '=', record.barcode.strip()),
                ('id', '!=', record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("El código de barras '%s' ya está asignado al producto '%s'. "
                      "Cada producto debe tener un código de barras único.")
                    % (record.barcode, duplicate.name)
                )
