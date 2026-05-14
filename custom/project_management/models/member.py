
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProjectMember(models.Model):
    _name = 'project.member'
    _description = 'Integrante'
    _rec_name = 'employee_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    """MANY2ONE"""
    team_id = fields.Many2one(
        'project.team', string='Equipo', required=True, ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True, ondelete='cascade')
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)