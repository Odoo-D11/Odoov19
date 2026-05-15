from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError


class ExpenseTypeTicket(models.Model):
    _name = 'expense.type.ticket'
    _description = 'Tipo de Ticket'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    description = fields.Char(string='Descripción')
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Definir los tipos de ticket con sus descripciones
        required_tickets = [
            {
                "name": "Básico",
                "description": "1 pieza incluida mochila o artículo personal"
            },
            {
                "name": "Estándar",
                "description": "Equipaje de Mano 1 pieza incluida"
            },
            {
                "name": "Plus",
                "description": "Equipaje de Mano 1 pieza incluida (10 kg / cm.) y Equipaje documentado 1 pieza incluida (23 kg / cm.)"
            },
            {
                "name": "Premium",
                "description": "Equipaje de Mano 1 pieza incluida (10 kg / cm.). Equipaje documentado 1 pieza incluida (23 kg / cm.). Reembolso incluido solo antes de la partida"
            }
        ]

        # Crear los tipos de ticket que faltan
        for ticket_data in required_tickets:
            if ticket_data["name"] not in existing_names:
                self.create(ticket_data)
