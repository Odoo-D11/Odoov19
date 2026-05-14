from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..utils.utils import normalize_string, similar, convert_first_letter_to_uppercase
import string
import re


class ResCity(models.Model):
    _name = 'res.city'
    _description = 'Ciudad'
    _order = 'name asc'
    _rec_name = 'name'

    """MANY2ONE"""
    state_id = fields.Many2one(
        'res.country.state', string='Estado', required=True)
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)

    @staticmethod
    def capitalize_parenthesis(text):
        # Capitaliza la primera letra de cada palabra y también la primera letra dentro de paréntesis
        # Capitaliza cada palabra normalmente
        text = string.capwords(text)
        # Capitaliza la primera letra después de un paréntesis de apertura
        def repl(match):
            return '(' + match.group(1).upper() + match.group(2)
        return re.sub(r'\((\w)([^)]*)', repl, text)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            normalized_name = normalize_string(vals.get('name', ''))
            state_id = vals.get('state_id', )
            self.env.cr.execute(
                """SELECT name, id FROM res_city WHERE state_id = %s""", (state_id,))
            cities = self.env.cr.dictfetchall()
            for city_id in cities:
                if similar(normalize_string(city_id['name']), normalized_name) > 0.8:
                    raise ValidationError(
                        _("La ciudad %s ya existe en el departamento seleccionado, por favor verifique e intente nuevamente.") %
                        city_id['name'])
            if 'name' in vals:
                vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(ResCity, self).create(vals_list)

    def write(self, vals):
        for rec in self:
            normalized_name = normalize_string(vals.get('name', rec.name))
            state_id = vals.get('state_id', rec.state_id.id)
            self.env.cr.execute("""SELECT name, id FROM res_city WHERE state_id = %s AND id != %s""",
                                (state_id, rec.id))
            cities = self.env.cr.dictfetchall()
            for city_id in cities:
                if similar(normalize_string(city_id['name']), normalized_name) > 0.8:
                    raise ValidationError(
                        _("La ciudad %s ya existe en el departamento seleccionado, por favor verifique e intente nuevamente.") %
                        city_id['name'])
        """CONVIERTE LA PRIMERA LETRA EN MAYÚSCULA"""
        if 'name' in vals:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(ResCity, self).write(vals)
