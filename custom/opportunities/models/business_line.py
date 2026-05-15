
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils.utils import convert_first_letter_to_uppercase


class TypeBusinessLine(models.Model):
    _name = 'opportunity.type.business.line'
    _description = 'Tipo de línea de negocio'
    _order = 'name asc'
    _rec_name = 'name'

    """ONE2MANY"""
    business_line_ids = fields.One2many(
        'opportunity.business.line', 'type_business_line_id', string='Líneas de negocio')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Ciberseguridad", "Outsourcing TI", "Cloud & Networking",
                          "Infraestructura Física", "Soluciones Software", "Smart Cities"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})


class BusinessLine(models.Model):
    _name = 'opportunity.business.line'
    _description = 'Línea de negocio'
    _order = 'type_business_line_id asc'
    _rec_name = 'type_business_line_id'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', readonly=True, ondelete='cascade', )
    type_business_line_id = fields.Many2one(
        'opportunity.type.business.line', string='Tipo de línea de negocio', required=True)
    percentage_id = fields.Many2one(
        'opportunity.percentage', string='Porcentaje', required=True)

    @api.constrains('percentage_id')
    def _check_percentage(self):
        for rec in self:
            lines = self.search([('lead_id', '=', rec.lead_id.id), ('id', '!=', rec.id)])
            total_percentage = sum(
                int(line.percentage_id.percentage[:-1]) for line in lines if line.percentage_id and line.percentage_id.percentage[:-1].isdigit())
            if rec.percentage_id:
                total_percentage += int(rec.percentage_id.percentage[:-1])
            if total_percentage > 100:
                raise ValidationError(
                    _("El porcentaje total de las líneas de negocio no puede ser mayor al 100%."))
