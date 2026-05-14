
from odoo import fields, models


class PurchaseMember(models.Model):
    _name = "purchase.member"
    _description = "Integrante"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "employee_id"

    """ONE2MANY"""
    assigned_projects_ids = fields.One2many(
        "assigned.project", "member_id", string="Proyectos Asignados")
    """MANY2ONE"""
    employee_id = fields.Many2one(
        "hr.employee", string="Empleado", required=True)
    team_id = fields.Many2one("purchase.team", string="Equipo", required=True)
    """CHAR"""
    team_name = fields.Char(
        related="team_id.name", string="Nombre del Equipo", )
