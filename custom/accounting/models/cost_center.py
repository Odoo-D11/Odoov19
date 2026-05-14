# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from unidecode import unidecode
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class CostCenter(models.Model):
    _name = 'cost.center'
    _description = 'Centro de costo'
    _rec_name = 'analytical_account_id' 

    """MANY2ONE"""
    analytical_account_id = fields.Many2one(
        'analytical.account', string='Cuenta Analítica', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True,
                                  default=lambda self: self.env.company.currency_id, readonly=False)
    """CHAR"""
    code = fields.Char(string='Referencia', required=True)
    """FLOAT"""
    count_income = fields.Float(
        string='Ingresos', required=False, readonly=True)
    count_expense = fields.Float(
        string='Egresos', required=False, readonly=True)

    @api.depends('analytical_account_id', 'code')
    def _compute_display_name(self):
        for rec in self:
            if rec.analytical_account_id and rec.code:
                rec.display_name = '[' + rec.code + '] ' + \
                    rec.analytical_account_id.name
            else:
                rec.display_name = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'code' in vals and 'analytical_account_id' in vals:
                analytical_account = self.env['analytical.account'].browse(
                    vals['analytical_account_id'])
                if analytical_account:
                    # Asegurarse de que el código termine con el sufijo de la cuenta analítica
                    if not vals['code'].endswith(analytical_account.code):
                        raise ValidationError(
                            "El código del centro de costo debe terminar con el sufijo de la cuenta analítica: %s" % analytical_account.code)
        return super(CostCenter, self).create(vals_list)
    
    def write(self, vals):
        for rec in self:
            if 'code' in vals or 'analytical_account_id' in vals:
                analytical_account_id = vals.get(
                    'analytical_account_id', rec.analytical_account_id.id)
                code = vals.get('code', rec.code)
                analytical_account = self.env['analytical.account'].browse(
                    analytical_account_id)
                if analytical_account:
                    # Asegurarse de que el código termine con el sufijo de la cuenta analítica
                    if not code.endswith(analytical_account.code):
                        raise ValidationError(
                            "El código del centro de costo debe terminar con el sufijo de la cuenta analítica: %s" % analytical_account.code)
        return super(CostCenter, self).write(vals)

    def action_view_analyze_income(self):
        pass

    def action_view_analyze_expenses(self):
        pass
    
    