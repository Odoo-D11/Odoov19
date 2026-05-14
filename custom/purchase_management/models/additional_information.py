
from odoo import api, fields, models, _


class PurchaseAdditionalInformation(models.Model):
    _name = 'purchase.additional.information'
    _description = 'Información adicional'
    _rec_name = 'request_quotation_id'

    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de cotización', ondelete='cascade', readonly=True,)
    destination_id = fields.Many2one(
        'res.city', string='Ciudad destino', readonly=True)
    """SELECTION"""
    location_delivery = fields.Selection([
        ('warehouse', 'Bodega'),
        ('field', 'Campo')
    ], string='Ubicación de entrega', readonly=True)
    """CHAR"""
    previous_evidence = fields.Char(string="Evidencia previa?", readonly=True)
    suggested_supplier_ids = fields.Char(
        string="Proveedores sugeridos", readonly=True)
    """BOOLEAN"""
    bugeted = fields.Boolean(string='Esta dentro del presupuesto?',
                             default=False, readonly=True)
    """FLOAT"""
    estimated_price = fields.Float(string='Precio estimado', readonly=True, digits=(12, 0))
