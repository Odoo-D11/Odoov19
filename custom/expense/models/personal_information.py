from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import re
import string


class ExpensePersonalInformation(models.Model):
    _name = 'expense.personal.information'
    _description = 'Información personal'
    _rec_name = 'partner_id'

    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', readonly=True)
    """MANY2ONE"""
    partner_id = fields.Many2one(
        'res.partner', string='Contacto', required=True, domain="[('is_employee', '=', True), ('id', '=', sequence)]")
    identification_type_id = fields.Many2one(
        'identification.type', string='Tipo de identificación', domain="[('code', 'not in', ('NIT', 'VAT', 'PAS'))]", required=True
    )
    country_id = fields.Many2one('res.country', string='País', domain="[('code', '=', 'CO')]",
                                 default=lambda self: self.env.ref('base.co'))
    """CHAR"""
    email = fields.Char(string='Correo electrónico', required=True)
    phone = fields.Char(string='Teléfono', required=True)
    nuid = fields.Char(string='Número de identificación', required=True)
    job_title = fields.Char(string='Cargo', required=True)
    """DATE"""
    birth_date = fields.Date(string='Fecha de nacimiento', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'job_title' in vals and vals['job_title']:
                vals['job_title'] = string.capwords(vals['job_title'])
            if 'phone' in vals and vals['phone']:
                phone = vals['phone'].replace(' ', '').replace('-', '')
                if phone.isdigit() and len(phone) >= 7:
                    vals['phone'] = phone[:3] + ' ' + phone[3:]
        return super(ExpensePersonalInformation, self).create(vals_list)

    def write(self, vals):
        for record in self:
            if 'job_title' in vals and vals['job_title']:
                vals['job_title'] = string.capwords(vals['job_title'])
            if 'phone' in vals and vals['phone']:
                phone = vals['phone'].replace(' ', '').replace('-', '')
                if phone.isdigit() and len(phone) >= 7:
                    vals['phone'] = phone[:3] + ' ' + phone[3:]
        return super(ExpensePersonalInformation, self).write(vals)
