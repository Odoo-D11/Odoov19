# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class InheritedResCountryState(models.Model):
    _inherit = 'res.country.state'

    """ONE2MANY"""
    city_ids = fields.One2many('res.city', 'state_id', string='Ciudades')
    """MANY2ONE"""
    country_id = fields.Many2one('res.country', string='País', required=True)
    """CHAR"""
    display_name = fields.Char(string='Nombre para mostrar', compute='_compute_display_name')

    @api.depends('name', 'country_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.name} ({record.country_id.code})"
