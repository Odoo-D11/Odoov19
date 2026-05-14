
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseAdministrativeExpense(models.Model):
    _name = 'purchase.administrative.expense'
    _description = 'Gasto administrativo'
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    """ONE2MANY"""
    product_line_ids = fields.One2many(
        'purchase.administrative.expense.line', 'expense_id', string='Productos')
    """MANY2ONE"""
    partner_id = fields.Many2one(
        'res.partner', string='Proveedor', required=True, domain="[('is_supplier', '=', True)]")
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id)
    enterprise_id = fields.Many2one(
        "purchase.enterprise", string="Empresa", )
    project_id = fields.Many2one(
        "project.management", string="Proyecto", required=True, domain="[('category_id', '!=', False)]")
    type_id = fields.Many2one(
        "request.type", string="Tipo de Solicitud", required=True, domain="[('name', '=', 'Servicios')]")
    """CHAR"""
    reference = fields.Char(string='Referencia', readonly=True,
                            required=True, copy=False, default='Nueva')
    subject = fields.Char(string="Asunto", required=True)
    payment_term = fields.Char(
        string='Plazo de pago', required=True, default="30 días")
    """FLOAT"""
    trm = fields.Float(string='TRM', digits=(12, 2))
    """MONETARY"""
    total = fields.Monetary(string='Total', currency_field='currency_id')
    """DATE"""
    """TEXT"""
    reason = fields.Text(string="Motivo del gasto", required=True)
    """SELECTION"""
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('caused', 'Causado'),
        ('paid', 'Pagado'),
    ], string='Estado', default='draft', readonly=True,)

    @api.onchange("currency_id")
    def _onchange_currency_id(self):
        """
        Obtiene el TRM. 
        NOTA: El TRM se obtiene de la última tasa registrada en res.currency.rate para la moneda seleccionada.
        """
        for rec in self:
            rec.trm = False
            if not rec.currency_id or rec.currency_id.name == "COP":
                continue
            try:
                rate = self.env['res.currency.rate'].search([
                    ('currency_id', '=', rec.currency_id.id),
                    ('company_id', '=', rec.env.company.id),
                ], order='name desc', limit=1)
                if rate:
                    rec.trm = rate.inverse_company_rate
            except Exception as e:
                continue

    @api.model
    def get_admin_expense_lines(self, expense_id):
        """Retorna las líneas de productos del gasto para el widget AdminExpenseBoard."""
        if not expense_id:
            return []
        return self.env['purchase.administrative.expense.line'].search_read(
            [('expense_id', '=', expense_id)],
            ['id', 'name', 'qty', 'price_unit', 'subtotal'],
            order='sequence, id',
        )

    @api.model
    def get_expense_line_view_id(self):
        """Retorna el ID de la vista para gestionar las líneas de servicio."""
        data = self.env['ir.model.data'].sudo().search_read(
            [('module', '=', 'purchase_management'),
             ('name', '=', 'view_purchase_administrative_expense_form_add_product')],
            ['res_id']
        )
        return data[0]['res_id'] if data else False

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res['type_id'] = self.env['request.type'].search(
            [('name', '=', 'Servicios')], limit=1).id
        return res
