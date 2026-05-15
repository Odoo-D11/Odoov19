
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils.utils import convert_first_letter_to_uppercase


class AssociativeFigureLine(models.Model):
    _name = 'opportunity.associative.figure.line'
    _description = 'Línea de Figura Asociativa'
    _rec_name = 'enterprise_id'

    """MANY2ONE"""
    enterprise_id = fields.Many2one(
        'res.partner', string='Empresa', required=True, domain="[('is_business', '=', True)]")
    percentage_id = fields.Many2one(
        'opportunity.percentage', string='Participación', required=True)
    lead_id = fields.Many2one('opportunity', string='Oportunidad', readonly=True)

    @api.constrains('enterprise_id', 'lead_id')
    def _check_enterprise_id(self):
        for record in self:
            if record.lead_id and record.lead_id.enterprise_id and record.enterprise_id:
                # Normalizamos los nombres a minúsculas y quitamos espacios en blanco extra
                lead_name = record.lead_id.enterprise_id.name.lower().strip()
                enterprise_name = record.enterprise_id.name.lower().strip()
                # Si uno de los nombres se encuentra dentro del otro, se considera que coinciden
                if lead_name in enterprise_name or enterprise_name in lead_name:
                    raise ValidationError(_(
                        "La empresa {} ya está registrada como empresa líder en este registro. "
                        "Por favor, selecciona otra empresa o verifica que la empresa elegida sea la correcta antes de continuar."
                    ).format(record.enterprise_id.name))
                # No permite duplicados en las líneas de figura asociativa
                if self.search_count([
                        ('lead_id', '=', record.lead_id.id),
                        ('enterprise_id', '=', record.enterprise_id.id)]) > 1:
                    raise ValidationError(_(
                        "La empresa {} ya está registrada como empresa asociativa en este registro. "
                        "Por favor, selecciona otra empresa o verifica que la empresa elegida sea la correcta antes de continuar."
                    ).format(record.enterprise_id.name))


class AssociativeFigure(models.Model):
    _name = 'opportunity.associative.figure'
    _description = 'Figura Asociativa'
    _order = 'name asc'
    _rec_name = 'name'

    """ONE2MANY"""
    lead_ids = fields.One2many(
        'opportunity', 'associative_figure_id', string='Oportunidades')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Unión temporal", "Consorcio"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(AssociativeFigure, self).create(vals_list)

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = convert_first_letter_to_uppercase(vals['name'])
        return super(AssociativeFigure, self).write(vals)
