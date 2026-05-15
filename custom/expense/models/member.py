
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseMember(models.Model):
    _name = 'expense.member'
    _description = 'Integrante'
    _rec_name = 'employee_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    """MANY2ONE"""
    team_id = fields.Many2one(
        'expense.team', string='Equipo', required=True, ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, ondelete='cascade')
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)
