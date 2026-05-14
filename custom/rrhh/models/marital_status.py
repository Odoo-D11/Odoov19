
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class HrMaritalStatus(models.Model):
    _name = 'hr.marital.status'
    _description = 'Estado civil'
    _rec_name = 'name'
    _order = 'name desc'

    """ONE2MANY"""
    employee_ids = fields.One2many(
        'hr.employee', 'marital_status_id', string='Empleados',)
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)

    @api.model
    def init(self):
        existing_names = self.search([]).mapped("name")
        required_names = ["Soltero(a)", "Casado(a)", "Unión libre",
                          "Divorciado(a)", "Viudo(a)", "Separado(a)",]
        missing_names = [
            name for name in required_names if name not in existing_names]
        if missing_names:
            for name in missing_names:
                self.create({'name': name})
