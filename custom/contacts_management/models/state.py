# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class InheritedResCountryState(models.Model):
    _inherit = 'res.country.state'

    """ONE2MANY"""
    city_ids = fields.One2many('res.city', 'state_id', string='Ciudades')
    """MANY2ONE"""
    country_id = fields.Many2one('res.country', string='País', required=True)
