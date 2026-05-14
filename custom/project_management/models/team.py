
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProjectTeam(models.Model):
    _name = 'project.team'
    _description = 'Equipo'
    _rec_name = 'name'

    """ONE2MANY"""
    member_ids = fields.One2many(
        'project.member', 'team_id', string='Miembros')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        categories = [
            "Gerencia",
            "Operaciones",
            "Contabilidad",
        ]
        existing = set(self.search([]).mapped("name"))
        for name in categories:
            if name not in existing:
                self.create({"name": name})
