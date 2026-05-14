
from odoo import fields, models, api


class PurchaseTeam(models.Model):
    _name = "purchase.team"
    _description = "Equipo"
    _rec_name = "name"

    """ONE2MANY"""
    member_ids = fields.One2many(
        "purchase.member", "team_id", string="Integrantes")
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)

    @api.model
    def init(self):
        existing_names = self.search([]).mapped("name")
        required_names = [
            "Compras",
            "Sagrilaft"
        ]
        missing_names = [
            name for name in required_names if name not in existing_names]

        for name in missing_names:
            self.create({
                "name": name
            })
