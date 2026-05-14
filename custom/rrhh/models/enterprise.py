
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from ..utils.utils import convert_first_letter_to_uppercase
import string


class HrEnterprise(models.Model):
    _name = 'hr.enterprise'
    _description = 'Compañía'
    _rec_name = 'name'
    _order = 'name asc'

    """ONE2MANY"""
    employee_ids = fields.One2many(
        'hr.employee', 'enterprise_id', string='Empleados',)
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        existing_names = self.search([]).mapped("name")
        required_names = ["Tsg The It Experts Sas", "Novacom Net Sas",
                          "Knox It Sas", "Union Temporal Salud",
                          "Union Temporal Movilidad", "UT Tecnologias Integradas 2023",
                          "It Busines Talent", "Kreivo Sas", "Ut Alcaldia De Bogota Mesa 2024",
                          "Consorcio Llano Seguro 2024", "Union Temporal Scb 2024",
                          "Union Temporal Scj 2024", "Union Temporal Ciberseguridad 2024",
                          "Ut Gestion Integral Centros De Datos 2025"]
        missing_names = [
            string.capwords(name) for name in required_names if string.capwords(name) not in existing_names]
        if missing_names:
            for name in missing_names:
                self.create({"name": name})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals:
                vals['name'] = string.capwords(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = string.capwords(vals['name'])
        return super().write(vals)
