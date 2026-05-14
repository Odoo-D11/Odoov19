
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup


class InheritPurchaseManagementResPartner(models.Model):
    _inherit = 'res.partner'

    """MANY2MANY"""
    product_category_ids = fields.Many2many(
        'warehouse.product.category', string='Categorías')
    """MANY2ONE"""
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id)
    """CHAR"""
    payment_term = fields.Char(string='Plazo de pago', required=True, default='30 días')
    """SELECTION"""
    qualification = fields.Selection([
        ('0', '0 - Ninguna'),
        ('1', '1 - Muy Malo'),
        ('2', '2 - Malo'),
        ('3', '3 - Regular'),
        ('4', '4 - Bueno'),
        ('5', '5 - Muy Bueno'),
    ], string='Calificación', readonly=True, default='0')
    sagrilaft_state = fields.Selection([
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
    ], string='Estado SAGRILAFT', readonly=True,)
    """DATE"""
    sagrilaft_expiration_date = fields.Date(
        string='Fecha de próxima aprobación', readonly=True)
    """BOOLEAN"""
    is_supplier = fields.Boolean(string='Proveedor', default=False,)

    def action_notify_sagrilaft_approval(self):
        template = self.env.ref(
            'purchase_management.email_template_sagrilaft_request_approval')
        team = self.env['purchase.team'].sudo().search(
            [('name', '=', 'Sagrilaft')], limit=1)
        if len(team.member_ids) == 0:
            raise UserError(
                _('No hay miembros asignados al equipo de SAGRILAFT. Por favor, contáctese con el administrador del sistema.'))
        for e in team.member_ids:
            template.send_mail(self.id, email_values={
                'email_to': e.employee_id.work_email or '',
            })
        for partner in self:
            msg = Markup(
                "<span>Se ha <span style='color: #017e84;'>notificado</span> la creación del proveedor y se encuentra a la espera de la aprobación por parte de <span style='color: #017e84;'>SAGRILAFT</span>.</span>")
            partner.message_post(body=msg)
        self.sagrilaft_state = 'pending'

    def action_approve_sagrilaft(self):
        if self.sagrilaft_state != 'pending':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('La aprobación solo puede realizarse en proveedores con estado pendiente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'name': 'Odoo',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.management.approval.sagrilaft.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_state': 'approve',
            },
        }

    def action_reject_sagrilaft(self):
        if self.sagrilaft_state != 'pending':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El rechazo solo puede realizarse en proveedores con estado pendiente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        return {
            'name': 'Odoo',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.management.approval.sagrilaft.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_state': 'reject',
            },
        }
