
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase
import string
# import ollama


class PurchaseManagementOrder(models.Model):
    _name = 'purchase.management.order'
    _description = 'Orden de compra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'reference'

    """ONE2MANY"""
    product_line_ids = fields.One2many(
        'purchase.management.order.line', 'order_id', string='Líneas de Orden de Compra')
    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de Cotización', required=True, ondelete='cascade')
    type_id = fields.Many2one(
        "request.type", string="Tipo de Solicitud", required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Proveedor', required=True, domain="[('is_supplier', '=', True)]")
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, )
    enterprise_id = fields.Many2one(
        "purchase.enterprise", string="Empresa", )
    project_id = fields.Many2one(
        "project.management", string="Proyecto", required=True, domain="[('category_id', '!=', False)]")
    """CHAR"""
    reference = fields.Char(string='Referencia', readonly=True,
                            required=True, copy=False, default='Nueva')
    subject = fields.Char(string="Asunto", required=True)
    payment_term = fields.Char(string='Plazo de pago', required=True)
    """FLOAT"""
    trm = fields.Float(string='TRM', digits=(12, 0))
    """MONETARY"""
    total = fields.Monetary(
        string='Total', compute='_compute_total', store=True,
        currency_field='currency_id')
    """DATE"""
    trm_date = fields.Date(string='Fecha TRM', readonly=True)
    delivery_date = fields.Date(string='Fecha de entrega', required=True)
    """TEXT"""
    reason = fields.Text(string="Motivo de la compra", required=True)
    """ENTREGA PERSONALIZADA"""
    delivery_contact_name = fields.Char(string='Nombre contacto de entrega')
    delivery_email = fields.Char(string='Correo de entrega')
    delivery_phone = fields.Char(string='Teléfono de entrega')
    delivery_address = fields.Text(string='Dirección de entrega')
    """BOOLEAN"""
    locked = fields.Boolean(string='Bloqueado', default=False, readonly=True)
    """SELECTION"""
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('sent', 'Enviado'),
        ('caused', 'Causado'),
        ('paid', 'Pagado'),
    ], string='Estado', default='draft', readonly=True,)

    def action_lock(self):
        self.locked = True

    def action_unlock(self):
        if not self.env.user.has_group('purchase_management.group_manager_purchase_management'):
            raise UserError(
                _('Solo un administrador de compras puede desbloquear la orden.'))
        self.locked = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'delivery_contact_name' in vals and vals['delivery_contact_name']:
                vals['delivery_contact_name'] = string.capwords(vals['delivery_contact_name'])
            if 'delivery_address' in vals and vals['delivery_address']:
                vals['delivery_address'] = convert_first_letter_to_uppercase(
                    vals['delivery_address'])
        return super(PurchaseManagementOrder, self).create(vals_list)

    def write(self, vals):
        _editable_when_locked = {'locked', 'message_ids',
                                 'message_follower_ids', 'activity_ids'}
        for record in self:
            if record.locked and not (set(vals.keys()) <= _editable_when_locked):
                raise UserError(
                    _('La orden de compra está bloqueada. Desbloquéala antes de realizar cambios.'))
        return super().write(vals)

    @api.depends('product_line_ids.subtotal')
    def _compute_total(self):
        for order in self:
            order.total = sum(order.product_line_ids.mapped('subtotal'))

    @api.onchange('partner_id', 'request_quotation_id')
    def _onchange_populate_from_quotation(self):
        if not self.partner_id or not self.request_quotation_id:
            return
        quotation = self.env['quotation.quotation'].search([
            ('request_quotation_id', '=', self.request_quotation_id.id),
            ('partner_id', '=', self.partner_id.id),
            ('awarded', '=', True),
        ], limit=1)
        if quotation:
            self.currency_id = quotation.currency_id
            self.trm = quotation.trm
            self.trm_date = quotation.trm_date

    def action_send(self):
        self.ensure_one()
        if not self.enterprise_id:
            raise ValidationError(
                _('Debe seleccionar una empresa antes de enviar la orden. Por favor, verifique e intente nuevamente.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Odoo'),
            'res_model': 'purchase.order.send.mail.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
            },
        }

    def action_print_order(self):
        self.ensure_one()
        if not self.enterprise_id:
            raise ValidationError(
                _('Debe seleccionar una empresa antes de imprimir la orden. Por favor, verifique e intente nuevamente.'))
        return self.env.ref('purchase_management.action_report_purchase_order').report_action(self)

    def action_cause(self):
        self.ensure_one()
        if not self.enterprise_id:
            raise ValidationError(
                _('Debe seleccionar una empresa antes de causar la orden. Por favor, verifique e intente nuevamente.'))
        self.sudo().state = 'caused'
        self.sudo().message_post(body=Markup(
            "<span>La orden de compra ha sido <span style='color: #017e84;'>causada</span>.</span>"))

    def action_pay(self):
        self.ensure_one()
        if not self.enterprise_id:
            raise ValidationError(
                _('Debe seleccionar una empresa antes de pagar la orden. Por favor, verifique e intente nuevamente.'))
        self.sudo().state = 'paid'

    @api.model
    def get_add_product_form_view_id(self):
        data = self.env['ir.model.data'].sudo().search_read(
            [
                ("module", "=", "purchase_management"),
                ("name", "=", "view_purchase_management_order_form_add_product"),
            ],
            ["res_id"]
        )
        return data[0]['res_id'] if data else False

    def action_view_traceability(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.request_quotation_id.reference,
            'res_model': 'request.quotation',
            'view_mode': 'form',
            'res_id': self.request_quotation_id.id,
            'target': 'current',
        }
