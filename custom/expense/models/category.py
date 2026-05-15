
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseCategory(models.Model):
    _name = 'expense.category'
    _description = 'Categoría'
    _rec_name = 'name'
    _order = 'name desc'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    display_name = fields.Char(
        string='Nombre para mostrar', compute='_compute_display_name', store=True,)

    @api.model
    def init(self):
        categories = [
            "Tiquetes y vuelos",
            "Viáticos (Alimentación, Hospedaje, etc.)",
        ]
        existing = set(self.search([]).mapped("name"))
        for name in categories:
            if name not in existing:
                self.create({"name": name})

    @api.depends('name')
    def _compute_display_name(self):
        for record in self:
            if record.name == "Viáticos (Alimentación, Hospedaje, etc.)":
                record.display_name = "[VIAT] " + record.name
            elif record.name == "Tiquetes y vuelos":
                record.display_name = "[TIQ] " + record.name
