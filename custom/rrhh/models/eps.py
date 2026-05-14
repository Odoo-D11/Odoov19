
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class HrEps(models.Model):
    _name = 'hr.eps'
    _description = 'EPS'
    _rec_name = 'name'

    """ONE2MANY"""
    employee_ids = fields.One2many(
        'hr.employee', 'eps_id', string='Empleados',)
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        existing_names = self.search([]).mapped("name")
        required_names = [
            "Nueva Eps",
            "Sanitas",
            "SURA",
            "Salud Total",
            "Compensar",
            "Coomeva",
            "Famisanar",
            "Savia Salud",
            "Medimás",
            "Colmena",
            "Mutual SER",
            "Cafesalud",
        ]
        missing_names = [
            name for name in required_names if name not in existing_names]

        for name in missing_names:
            self.create({
                "name": name
            })
