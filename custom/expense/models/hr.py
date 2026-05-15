
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError

# No se actualmente porque cada campo que quiero agregar en hr.employee debe tambien
# agregarse en hr.employee.public (Revisar motivo)


class InheritExpenseHrEmployee(models.Model):
    _inherit = 'hr.employee'

    """FLOAT"""
    bag = fields.Float(string='Bolsa', digits=(16, 0), readonly=True)
    """BOOLEAN"""
    blocked = fields.Boolean(string='Bloqueado', readonly=True)


class InheritExpenseHrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    """FLOAT"""
    bag = fields.Float(string='Bolsa', digits=(16, 0), readonly=True)
    """BOOLEAN"""
    blocked = fields.Boolean(string='Bloqueado', readonly=True)
