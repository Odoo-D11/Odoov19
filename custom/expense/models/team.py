
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseTeam(models.Model):
    _name = 'expense.team'
    _description = 'Equipo'
    _rec_name = 'name'

    """ONE2MANY"""
    member_ids = fields.One2many(
        'expense.member', 'team_id', string='Integrantes del equipo')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Contabilidad", "Tesorería"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        for name in missing_names:
            self.create({
                "name": name
            })
