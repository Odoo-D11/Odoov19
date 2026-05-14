
from odoo import api, fields, models


class PurchaseTypeCommercialTerm(models.Model):
    _name = 'purchase.type.commercial.term'
    _description = 'Tipo de Condición Comercial'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    prefix = fields.Char(string='Prefijo', required=True)

    @api.model
    def init(self):
        existing_records = self.search([]).mapped("name")
        required_records = [
            {"name": "INCLUYE TRANSPORTE", "prefix": "IT"},
            {"name": "MAYOR DESCUENTO", "prefix": "MD"},
            {"name": "MAYOR PLAZO DE CRÉDITO", "prefix": "MPC"},
            {"name": "SIN ANTICIPOS", "prefix": "SA"},
            {"name": "NEGOCIAR CON FABRICANTE", "prefix": "NF"},
            {"name": "MENOR TIEMPO DE ENTREGA", "prefix": "MTE"},
            {"name": "OFERTA EN VALOR DE MANTENIMIENTO", "prefix": "OVM"},
            {"name": "MAYOR GARANTÍA", "prefix": "MG"},
            {"name": "MENOR COSTO", "prefix": "MC"},
            {"name": "ÚNICO OFERENTE", "prefix": "UO"},
            {"name": "INCLUYE CONTRATO", "prefix": "IC"},
            {"name": "INCLUYE PÓLIZA", "prefix": "IP"}
        ]

        for record in required_records:
            if record["name"] not in existing_records:
                self.create({
                    "name": record["name"],
                    "prefix": record["prefix"]
                })

    @api.depends('name', 'prefix')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.prefix}] {record.name}"


class PurchaseCommercialTerm(models.Model):
    _name = 'purchase.commercial.term'
    _description = 'Condiciones Comerciales de Compra'

    """MANY2ONE"""
    quotation_id = fields.Many2one(
        'quotation.quotation', string='Cotización', ondelete='cascade')
    type_id = fields.Many2one(
        'purchase.type.commercial.term', string='Tipo de Condición Comercial', required=True)