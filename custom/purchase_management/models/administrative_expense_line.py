from odoo import api, fields, models
EXPENSE_LINE_NOTIFICATION_TYPE = "administrative_expense.line/update"


class PurchaseAdministrativeExpenseLine(models.Model):
    _name = 'purchase.administrative.expense.line'
    _description = 'Línea de servicio de gasto administrativo'
    _order = 'sequence, id'

    """MANY2ONE"""
    expense_id = fields.Many2one(
        'purchase.administrative.expense', string='Gasto administrativo',
        required=True, ondelete='cascade')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', compute='_compute_currency_id',)
    """MONETARY"""
    price_unit = fields.Monetary(
        string='Precio unitario', required=True, currency_field='currency_id')
    subtotal = fields.Monetary(
        string='Subtotal', compute='_compute_subtotal', store=True, currency_field='currency_id')
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', default=10)
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    """INTEGER"""
    qty = fields.Integer(string='Cantidad', required=True)

    @api.depends('expense_id')
    def _compute_currency_id(self):
        for record in self:
            record.currency_id = record.expense_id.currency_id if record.expense_id else self.env.company.currency_id

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for record in self:
            record.subtotal = record.qty * record.price_unit

    def _get_expense_channel(self):
        return f"administrative_expense_lines_{self.expense_id.id}"

    def _notify_expense_update(self):
        for rec in self:
            if not rec.expense_id:
                continue
            self.env['bus.bus']._sendone(
                rec._get_expense_channel(),
                EXPENSE_LINE_NOTIFICATION_TYPE,
                {'expense_id': rec.expense_id.id},
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_expense_update()
        return records

    def write(self, vals):
        res = super().write(vals)
        if res:
            self._notify_expense_update()
        return res

    def unlink(self):
        for rec in self:
            rec._notify_expense_update()
        return super().unlink()
