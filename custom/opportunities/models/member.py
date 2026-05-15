
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import string


class TeamMember(models.Model):
    _name = 'opportunity.team.member'
    _description = 'Integrante'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_id asc'
    _rec_name = 'employee_id'

    """MANY2MANY"""
    partner_ids = fields.Many2many('res.partner', string='Clientes')
    """MANY2ONE"""
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', required=True)
    team_id = fields.Many2one(
        'opportunity.team', string='Equipo', required=True)
    """CHAR"""
    email = fields.Char(
        string='Email', related='employee_id.work_email', readonly=False)
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', )
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)
