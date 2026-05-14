
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrEmployeeAdditionalIncome(models.Model):
    _name = 'hr.employee.additional.income'
    _description = 'Ingresos adicionales del empleado'

    """MANY2ONE"""
    income_type_id = fields.Many2one(
        'hr.income.type', string='Tipo de ingreso', required=True, )
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', )
