
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import string


class Team(models.Model):
    _name = 'opportunity.team'
    _description = 'Equipo'
    _order = 'name asc'
    _rec_name = 'name'

    """ONE2MANY"""
    members_ids = fields.One2many(
        'opportunity.team.member', 'team_id', string='Integrantes')
    """MANY2ONE"""
    leader_id = fields.Many2one('opportunity.team.member', string='Líder')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Comercial", "Preventa",
                          "Licitaciones", "Financiero"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})
