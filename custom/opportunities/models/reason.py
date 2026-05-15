

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils.utils import convert_first_letter_to_uppercase

class CrmLeadReason(models.Model):
    _name = 'opportunity.reason'
    _description = 'Motivo'
    _order = 'name asc'
    _rec_name = 'name'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Desierto el proceso", "No viable",
                          "No se cumple experiencia", "Aliado UT",
                          "Por incumbencia", "Indicadores Financieros",
                          "Duplicada", "No prioritario", "No se cumple requerimiento ponderable",
                          "Precio"]
        missing_names = [
            name for name in required_names if name not in existing_names]
        
        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})