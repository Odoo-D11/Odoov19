# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..utils.utils import normalize_string, similar, capitalize_first_letter


class IdentificationType(models.Model):
    _name = 'identification.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tipo de identificación'
    _rec_name = 'name'
    _order = 'name asc'

    """ONE2MANY"""
    partner_ids = fields.One2many(
        'res.partner', 'identification_type_id', string='Contactos')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    display_name = fields.Char(
        string='Nombre completo', compute='_compute_display_name', store=True)
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', )
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            if record.name not in ['NIT', 'VAT']:
                record.display_name = record.name + \
                    ' (' + record.code + \
                    ')' if record.name and record.code else record.name
            else:
                record.display_name = record.name if record.name else record.code

    @api.model_create_multi
    def create(self, vals_list):
        """UTILIZAR LA FUNCIÓN normalize_string PARA ELIMINAR TILDES Y CARACTERES ESPECIALES"""
        for vals in vals_list:
            normalized_name = normalize_string(vals.get('name', ''))
            self.env.cr.execute("""SELECT name FROM identification_type""")
            identification_types = self.env.cr.fetchall()
            for identification_type in identification_types:
                if similar(normalize_string(identification_type[0]), normalized_name) > 0.8:
                    raise ValidationError(
                        _("El tipo de identificación %s ya existe, por favor verifique e intente nuevamente.") %
                        identification_type[0])
        return super(IdentificationType, self).create(vals_list)

    def write(self, vals):
        """UTILIZAR LA FUNCIÓN normalize_string PARA ELIMINAR TILDES Y CARACTERES ESPECIALES"""
        for rec in self:
            normalized_name = normalize_string(vals.get('name', rec.name))
            self.env.cr.execute(
                """SELECT name FROM identification_type WHERE id != %s""", (rec.id,))
            identification_types = self.env.cr.fetchall()
            for identification_type in identification_types:
                if similar(normalize_string(identification_type[0]), normalized_name) > 0.8:
                    raise ValidationError(
                        _("El tipo de identificación %s ya existe, por favor verifique e intente nuevamente.") %
                        identification_type[0])
        return super(IdentificationType, self).write(vals)
