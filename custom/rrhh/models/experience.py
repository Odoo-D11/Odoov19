
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup
import string
from ..utils.utils import ( # type: ignore
    is_html_content_empty,
    convert_first_letter_to_uppercase,
)

class HrExperience(models.Model):
    _name = 'hr.experience'
    _description = 'Experiencia Laboral'
    _rec_name = 'enterprise'
    _order = 'start_date desc, id desc'

    def init(self):
        self.env.cr.execute("""
            ALTER TABLE hr_experience
            DROP CONSTRAINT IF EXISTS hr_experience_employee_id_fkey;
            ALTER TABLE hr_experience
            ADD CONSTRAINT hr_experience_employee_id_fkey
            FOREIGN KEY (employee_id) REFERENCES hr_employee(id) ON DELETE CASCADE;
        """)

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
            if vals.get('position'):
                vals['position'] = ' '.join(vals['position'].split()).title()
            if vals.get('enterprise'):
                vals['enterprise'] = ' '.join(vals['enterprise'].split()).title()
            if vals.get('description'):
                vals['description'] = convert_first_letter_to_uppercase(
                    ' '.join(vals['description'].split()))
        return super(HrExperience, self).create(vals_list)

    def write(self, vals):
        if 'position' in vals and vals['position']:
            vals['position'] = ' '.join(vals['position'].split()).title()
        if 'enterprise' in vals and vals['enterprise']:
            vals['enterprise'] = ' '.join(vals['enterprise'].split()).title()
        if 'description' in vals and vals['description']:
            vals['description'] = convert_first_letter_to_uppercase(
                ' '.join(vals['description'].split()))
        return super(HrExperience, self).write(vals)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(
                    _("La fecha de inicio no puede ser posterior a la fecha de fin."))