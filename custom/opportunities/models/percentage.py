
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class Percentage(models.Model):
    _name = 'opportunity.percentage'
    _description = 'Porcentaje'
    _rec_name = 'percentage'

    """CHAR"""
    percentage = fields.Char(string='Porcentaje',)

    @api.model
    def init(self):
        # Obtener los números existentes en el modelo
        existing_numbers = [int(
            num[:-1]) for num in self.search([]).mapped("percentage") if num.endswith('%')]

        # Crear los números que faltan del 1 al 100
        missing_numbers = [num for num in range(
            1, 101) if num not in existing_numbers]

        if missing_numbers:
            # Crear registros para los números faltantes
            for num in missing_numbers:
                self.create({"percentage": str(num) + "%"})

    @api.constrains('percentage')
    def _check_probability(self):
        for record in self:
            if record.percentage:
                if not record.percentage.endswith('%'):
                    raise ValidationError(
                        _("El porcentaje debe terminar con '%'"))
                if not record.percentage[:-1].isdigit():
                    raise ValidationError(
                        _("El porcentaje debe ser un número"))
                if int(record.percentage[:-1]) not in range(1, 101):
                    raise ValidationError(
                        _("El porcentaje debe estar entre 1 y 100"))
