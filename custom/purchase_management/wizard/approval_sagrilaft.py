# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup


class ApprovalSagrilaftWizard(models.TransientModel):
    _name = 'purchase.management.approval.sagrilaft.wizard'
    _description = 'Wizard para la aprobación o rechazo de SAGRILAFT'

    """MANY2ONE"""
    partner_id = fields.Many2one(
        'res.partner', string='Proveedor', readonly=True)
    """SELECTION"""
    state = fields.Selection([
        ('approve', 'Aprobar'),
        ('reject', 'Rechazar')
    ], string='Acción', readonly=True)
    """DATE"""
    sagrilaft_expiration_date = fields.Date(
        string='Fecha de próxima aprobación')
    """TEXT"""
    rejection_reason = fields.Text(string='Motivo del rechazo')

    def action_confirm(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("No se ha especificado un proveedor."))
        if self.state == 'approve':
            self.env['res.partner'].browse(self.partner_id.id).sudo().write({
                'sagrilaft_state': 'approved',
                'sagrilaft_expiration_date': self.sagrilaft_expiration_date,
            })
            msg = Markup(
                "<span>El proveedor ha sido <span style='color: #017e84;'>aprobado</span> en la verificación <span style='color: #017e84;'>SAGRILAFT</span>. "
                f"Próxima revisión: <span style='color: #017e84;'>{self.sagrilaft_expiration_date.strftime('%d/%m/%Y')}</span>.</span>"
            )
            self.partner_id.message_post(body=msg)
        elif self.state == 'reject':
            self.env['res.partner'].browse(self.partner_id.id).sudo().write({
                'sagrilaft_state': 'rejected',
            })
            msg = Markup(
                "<span>El proveedor ha sido <span style='color: #017e84;'>rechazado</span> en la verificación <span style='color: #017e84;'>SAGRILAFT</span>. "
                f"Motivo: {self.rejection_reason}</span>"
            )
            self.partner_id.message_post(body=msg)
        return {'type': 'ir.actions.act_window_close'}
