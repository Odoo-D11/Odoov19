
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class History(models.Model):
    _name = 'opportunity.history'
    _description = 'Historial de cambios'
    _rec_name = 'lead_id'
    _order = 'date desc'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, ondelete='cascade')
    member_id = fields.Many2one(
        'opportunity.team.member', string='Responsable', required=True,)
    reason_id = fields.Many2one(
        'opportunity.reason', string='Motivo', required=True,)
    """DATE"""
    date = fields.Date(string='Fecha', required=True, readonly=True,
                       default=fields.Date.context_today,)
    """HTML"""
    description = fields.Html(string='Descripción', readonly=True,)