
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class HrCompensationFund(models.Model):
    _name = 'hr.compensation.fund'
    _description = 'Caja de compensación'
    _rec_name = 'name'

    """ONE2MANY"""
    employee_ids = fields.One2many(
        'hr.employee', 'compensation_fund_id', string='Empleados')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = [
            "Cafam",
            "Colsubsidio",
            "Compensar",
            "Comfandi",
            "Comfamiliar Nariño",
            "Comfamiliar Huila",
            "Comfenalco Tolima",
            "Comfacauca"
        ]

        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})
