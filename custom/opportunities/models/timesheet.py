
from odoo import models, fields, api, _
from odoo .exceptions import ValidationError
from ..utils.utils import convert_first_letter_to_uppercase


class OpportunityTimesheet(models.Model):
    _name = 'opportunity.timesheet'
    _description = 'Tiempos de Oportunidad'
    _rec_name = 'lead_id'

    """MANY2ONE"""
    member_id = fields.Many2one(
        'opportunity.team.member', string='Responsable', required=True)
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, ondelete='cascade')
    """HTML"""
    description = fields.Html(string='Descripción', required=True)
    """DATETIME"""
    start_date = fields.Datetime(
        string='Fecha de inicio', required=True,)
    end_date = fields.Datetime(string='Fecha de fin',)
    """DATE"""
    date = fields.Date(string='Fecha', required=True,
                       compute='_compute_date',)
    """CHAR"""
    duration = fields.Char(
        string='Duración', compute='_compute_duration', readonly=True,)
    state = fields.Char(string='Estado', readonly=True,)

    @api.depends('start_date')
    def _compute_date(self):
        for record in self:
            if record.start_date:
                record.date = record.start_date.date()
            else:
                record.date = False

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                delta = abs(record.end_date - record.start_date)
                total_seconds = delta.total_seconds()
                days = int(total_seconds // 86400)
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                duration_str = ""
                if days:
                    duration_str += f"{days}d"
                if hours:
                    duration_str += " "
                    duration_str += f"{hours}h"
                if minutes:
                    if hours:
                        duration_str += " "
                    duration_str += f"{minutes}m"
                if seconds:
                    if hours or minutes:
                        duration_str += " "
                    duration_str += f"{seconds}s"
                record.duration = duration_str if duration_str else "0s"
            else:
                record.duration = ""
