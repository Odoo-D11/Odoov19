# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class InheritedResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        company = self.env['res.company'].search(
            [('id', '=', self.env.company.id)], limit=1).partner_id
        if 'partner_id' not in vals_list[0]:
            partner_vals = {
                'is_employee': True,
                'is_business': False,
                'is_supplier': False,
                'identification_type_id': company.identification_type_id.id,
                'vat': company.vat,
                'parent_id': company.id,
                'name': vals_list[0]['name'],
                'street': company.street,
                'state_id': company.state_id.id,
                'city_id': company.city_id.id,
                'country_id': company.country_id.id,
            }
            with self.env.cr.savepoint():
                self = self.with_context(skip_vat_validation=True)
                partner = self.env['res.partner'].search(
                    [('name', '=', vals_list[0]['name']), ('parent_id', '=', company.id)],
                    limit=1
                )
                if not partner:
                    partner = self.env['res.partner'].create(partner_vals)
                vals_list[0]['partner_id'] = partner.id
        user = super(InheritedResUsers, self).create(vals_list)
        if user.partner_id:
            user.partner_id.email = user.login
        return user

    def write(self, vals):
        if 'tz' in vals:
            with self.env.cr.savepoint():
                self = self.with_context(skip_tz_validation=True)
        return super(InheritedResUsers, self).write(vals)
