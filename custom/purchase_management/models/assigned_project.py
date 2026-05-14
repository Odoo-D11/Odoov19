
from odoo import models, fields


class PurchaseAssignedProject(models.Model):
    _name = "assigned.project"
    _description = "Proyecto Asignado"
    _rec_name = "project_id"

    """MANY2ONE"""
    project_id = fields.Many2one(
        "project.management", string="Proyecto", required=True,)
    member_id = fields.Many2one(
        "purchase.member", string="Integrante", ondelete="cascade")
