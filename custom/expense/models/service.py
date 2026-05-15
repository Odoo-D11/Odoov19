# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseService(models.Model):
    _name = 'expense.service'
    _description = 'Servicio'
    _order = 'name'
    _rec_name = 'name'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Hospedaje", "Transp. En Sitio", "Transp. Intermunicipal",
                          "Transp. Terminal", "Lavandería", "Alimentación",
                          "Impuestos Ingreso A Territorio", "Imprevistos"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        for name in missing_names:
            self.create({
                "name": name
            })
