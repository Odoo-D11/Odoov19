from odoo import models, fields, api, _
from ..utils.utils import convert_first_letter_to_uppercase, _clean_note_text


class ProductQuotationLine(models.Model):
    _name = 'product.quotation.line'
    _description = 'Lista de Productos en Cotización'
    _order = 'sequence, id'

    """MANY2ONE"""
    quotation_id = fields.Many2one(
        'quotation.quotation', string='Cotización', required=True, ondelete='cascade')
    request_line_id = fields.Many2one(
        'request.product.quotation.line', string='Línea de Solicitud',
        help='Referencia a la línea de producto en la solicitud de cotización')
    uom_id = fields.Many2one(
        'warehouse.uom', string='UdM', readonly=True, default=lambda self: self.env['warehouse.uom'].search([('name', '=', 'Unidad')], limit=1))
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, compute='_compute_currency_id', store=True)
    """FLOAT"""
    qty = fields.Float(string='Cantidad', digits=(16, 0))
    assigned_qty = fields.Float(string='Cant. asignada', digits=(16, 0), default=0)
    """MONETARY"""
    price_unit = fields.Monetary(
        string='Precio Unit.', currency_field='currency_id',)
    subtotal = fields.Monetary(
        string='Subtotal', compute='_compute_subtotal', currency_field='currency_id', store=True)
    """TEXT"""
    name = fields.Text(string='Nombre')
    """CHAR"""
    product_name = fields.Char(
        string='Nombre del Producto',
        help='Nombre del producto al que pertenece esta especificación (solo para notas)')
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', default=10)
    """SELECTION"""
    display_type = fields.Selection(
        [('line_note', 'Nota')],
        string='Tipo de línea',
    )

    @api.onchange('product_name')
    def _onchange_product_name(self):
        for line in self:
            if line.product_name:
                line.product_name = convert_first_letter_to_uppercase(
                    line.product_name)
            else:
                line.product_name = False

    @api.onchange('name')
    def _onchange_name(self):
        for line in self:
            if line.name and line.display_type == 'line_note':
                line.name = _clean_note_text(line.name)

    @api.depends('quotation_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = line.quotation_id.currency_id

    @api.depends('qty', 'price_unit', 'display_type')
    def _compute_subtotal(self):
        """Calcula el precio estimado basado en cantidad y precio unitario"""
        for line in self:
            # Las notas no tienen subtotal
            if line.display_type == 'line_note':
                line.subtotal = 0.0
            else:
                line.subtotal = (line.qty or 0.0) * (line.price_unit or 0.0)
