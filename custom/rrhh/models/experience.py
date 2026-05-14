
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup
import string
from ..utils.utils import ( # type: ignore
    is_html_content_empty,
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
)

class HrExperience(models.Model):
    _name = 'hr.experience'
    _description = 'Experiencia Laboral'
    _rec_name = 'enterprise'
    _order = 'start_date desc, id desc'

    """MANY2ONE"""
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', ondelete='cascade',)    
    """CHAR"""
    position = fields.Char(string='Cargo', required=True)
    enterprise = fields.Char(string='Empresa', required=True)
    """MANY2ONE"""
    city_id = fields.Many2one('res.city', string='Ciudad', required=False)
    """DATE"""
    start_date = fields.Date(string='Fecha de inicio', required=True)
    end_date = fields.Date(string='Fecha de fin', required=False)
    """TEXT"""
    description = fields.Text(string='Descripción',)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['position'] = string.capwords(vals.get('position', ''))
            vals['enterprise'] = string.capwords(vals.get('enterprise', ''))
            if vals.get('description'):
                vals['description'] = format_html_to_sentence_case(vals['description'])
        return super(HrExperience, self).create(vals_list)
    
    def write(self, vals):
        if 'position' in vals:
            vals['position'] = string.capwords(vals['position'])
        if 'enterprise' in vals:
            vals['enterprise'] = string.capwords(vals['enterprise'])
        if 'description' in vals and vals['description']:
            vals['description'] = format_html_to_sentence_case(vals['description'])
        return super(HrExperience, self).write(vals)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(
                    _("La fecha de inicio no puede ser posterior a la fecha de fin."))