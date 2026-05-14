from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from ..utils.utils import convert_first_letter_to_uppercase, _clean_special_chars, _clean_note_text


class RequestProductQuotationLine(models.Model):
    _name = "request.product.quotation.line"
    _description = "Lista de Productos en Solicitud de Cotización"
    _order = "request_quotation_id, sequence, id"

    """CAMPOS TÉCNICOS"""
    display_type = fields.Selection(
        selection=[('line_note', "Note")],
        default=False,
    )
    sequence = fields.Integer(string='Sequence', default=1)
    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        "request.quotation", string="Solicitud de cotización", ondelete="cascade")
    uom_id = fields.Many2one(
        "warehouse.uom", string="UdM", default=lambda self: self.env['warehouse.uom'].search([('name', '=', 'Unidad')], limit=1))
    warehouse_variant_id = fields.Many2one(
        'warehouse.product.variant', string='Variante', ondelete='set null')
    cost_center_id = fields.Many2one(
        'cost.center', string='Centro de costo', ondelete='set null')
    """FLOAT"""
    qty = fields.Float(string="Cantidad", digits=(16, 0), default=1)
    """TEXT"""
    name = fields.Text(string="Nombre", )
    """CHAR"""
    product_name = fields.Char('Nombre del producto')
    """TEXT"""
    sent_to_emails = fields.Text(
        string='Enviado a', help='Correos separados por coma a los que se ha enviado este producto.')

    @api.onchange('name')
    def _onchange_name(self):
        for line in self:
            if line.name:
                if line.display_type == 'line_note':
                    line.uom_id = False
                    line.name = _clean_note_text(line.name)
                else:
                    line.name = _clean_special_chars(line.name).title()

    def _get_product_channel_name(self, record_id):
        """Genera el nombre del canal para las notificaciones de productos"""
        return f"request_quotation_products{record_id}"

    def _notify_product_update(self, request_quotation_ids=None, reason="update"):
        rq_ids = set(request_quotation_ids or self.mapped(
            'request_quotation_id').ids)
        rq_ids.discard(False)
        if not rq_ids:
            return
        timestamp = fields.Datetime.now()
        bus = self.env['bus.bus']
        for record_id in rq_ids:
            channel_name = self._get_product_channel_name(record_id)
            bus._sendone(
                channel_name,
                'purchase_management.product/update',
                {
                    'request_quotation_id': record_id,
                    'reason': reason,
                    'timestamp': timestamp,
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # El widget (product_line_name) actualiza las secuencias correctas
            if 'sequence' not in vals or vals.get('sequence') is None:
                vals['sequence'] = 9999
        records = super(RequestProductQuotationLine, self).create(vals_list)
        records._notify_product_update(reason="create")
        return records

    def _resequence_lines(self, record_id, fk_field='request_quotation_id'):
        """ Crea las secuencias (1, 2, 3...) para todas las líneas"""
        lines = self.search([
            (fk_field, '=', record_id)
        ], order='sequence, id')
        for index, line in enumerate(lines, start=1):
            if line.sequence != index:
                # Usa SQL directo para evitar triggers y validaciones
                self.env.cr.execute(
                    "UPDATE request_product_quotation_line SET sequence = %s WHERE id = %s",
                    (index, line.id)
                )
        self.invalidate_model(['sequence'])

    def write(self, vals):
        result = super().write(vals)
        if result:
            self._notify_product_update(reason="write")
        return result

    def unlink(self):
        for line in self:
            if line.display_type == 'line_note':
                continue
            if line.request_quotation_id and line.request_quotation_id.state != 'draft':
                raise ValidationError(
                    _('No se pueden eliminar productos de la lista cuando la solicitud de cotización '
                      'no está en estado borrador. '))
        rq_ids = set(self.mapped('request_quotation_id').ids)
        result = super().unlink()
        if result:
            for rq_id in rq_ids:
                if rq_id:
                    self._resequence_lines(rq_id, 'request_quotation_id')
            self.env['request.product.quotation.line']._notify_product_update(
                reason="unlink",
            )
        return result
