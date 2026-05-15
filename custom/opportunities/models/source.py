
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class Source(models.Model):
    _name = 'opportunity.source'
    _description = 'Fuente'
    _order = 'name asc'
    _rec_name = 'name'

    """ONE2MANY"""
    lead_ids = fields.One2many(
        'opportunity', 'source_id', string='Oportunidades')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Secop - II", "Secop - I", "Ariba",
                          "Camara de comercio", "Ecopetrol - Siproe",
                          "Claro - Ivalua", "Oracle - Cloud", "Bid - Correo",
                          "Gep - Telefonica", "Relación comercial", "Bolsa mercantil",]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})
