
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseViewAttachment(models.TransientModel):
    _name = 'expense.view.attachment'
    _description = 'Ver adjuntos de gastos'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    expense_id = fields.Many2one(
        'expense.expense', string='Solicitud', required=True, readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', related='expense_id.employee_id', readonly=True)
    """BINARY"""
    attached_evidence = fields.Binary(string='Evidencia')
    attached_reimbursement = fields.Binary(string='Reembolso')
    """SELECTION"""
    view_mode = fields.Selection([
        ('evidence', 'Evidencia'),
        ('reimbursement', 'Reembolso')
    ], string='Modo de Vista', readonly=True,)
    """BOOLEAN"""
    evidence = fields.Boolean(string='¿Tiene Evidencia?', readonly=True)
    reimbursement = fields.Boolean(
        string='¿Tiene Reembolso?', readonly=True)

    def action_view_evidence(self):
        self.ensure_one()
        self.view_mode = 'evidence'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Odoo',
            'res_model': 'expense.view.attachment',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_view_reimbursement(self):
        self.ensure_one()
        self.view_mode = 'reimbursement'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Odoo',
            'res_model': 'expense.view.attachment',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class ExpenseRefundViewAttachment(models.TransientModel):
    _name = 'expense.refund.view.attachment'
    _description = 'Ver adjuntos de reintegros'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    refund_id = fields.Many2one(
        'expense.refund', string='Reintegro', required=True, readonly=True)
    """BINARY"""
    attached_document = fields.Binary(string='Evidencia adjunta')
