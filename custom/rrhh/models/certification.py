
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import string

class HrCertification(models.Model):
    _name = 'hr.certification'
    _description = 'Certificación'
    _rec_name = 'name'
    _order = 'date_start desc, id desc'

    """MANY2ONE"""
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', ondelete='cascade', index=True, required=True)
    """CHAR"""
    name = fields.Char(string='Nombre de la certificación', required=True)
    institution = fields.Char(string='Institución', required=True)
    """SELECTION"""
    certification_level = fields.Selection([
        ('bachiller', 'Bachiller'),
        ('tecnico', 'Técnico'),
        ('pregrado', 'Pregrado'),
        ('especializacion', 'Especialización'),
        ('maestria', 'Maestría'),
        ('doctorado', 'Doctorado'),
        ('diplomado', 'Diplomado'),
        ('certificaciones', 'Certificaciones')
    ], string='Nivel de certificación', required=True)
    """DATE"""
    date_start = fields.Date(string='Fecha de inicio', required=True)
    date_end = fields.Date(string='Fecha de finalización', required=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = ' '.join(vals['name'].split()).title()
            if vals.get('institution'):
                vals['institution'] = ' '.join(vals['institution'].split()).title()
        return super(HrCertification, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals and vals['name']:
            vals['name'] = ' '.join(vals['name'].split()).title()
        if 'institution' in vals and vals['institution']:
            vals['institution'] = ' '.join(vals['institution'].split()).title()
        return super(HrCertification, self).write(vals)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_start > record.date_end:
                raise ValidationError(_('La fecha de inicio no puede ser posterior a la fecha de finalización.'))