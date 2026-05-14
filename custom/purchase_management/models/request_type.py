
from odoo import fields, models, api


class RequestType(models.Model):
    _name = "request.type"
    _description = "Tipo de Solicitud de Cotización"
    _rec_name = "name"

    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    """BOOLEAN"""
    active = fields.Boolean(string="Activo", default=True)

    @api.model
    def init(self):
        categories = [
            "Productos",
            "Servicios",
        ]
        existing = set(self.search([]).mapped("name"))
        for name in categories:
            if name not in existing:
                self.create({"name": name})

    @api.depends('name')
    def _compute_display_name(self):
        for record in self:
            if record.name == "Productos":
                record.display_name = "[PROD] Productos (Bienes físicos, Ej. Tecnología, Portátiles, Firewall, UPS)"
            elif record.name == "Servicios":
                record.display_name = "[SERV] Servicios (Consultoría, mantenimiento, etc.)"
            elif record.name == "Mixtos":
                record.display_name = "[MIXT] Mixtos (Incluye productos y servicios)"
            else:
                record.display_name = record.name
