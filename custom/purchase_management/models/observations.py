
from odoo import models, fields, api, _
from ..utils.utils import convert_first_letter_to_uppercase


class PurchaseProjectObservationRecommendation(models.Model):
    _name = 'purchase.project.observation.recommendation'
    _description = 'Observaciones lider de proyecto, Recomendacion final, Comite'

    """MANY2ONE"""
    quotation_id = fields.Many2one(
        'quotation.quotation', string='Cotización', readonly=True, ondelete='cascade')
    """SELECTION"""
    team = fields.Selection([
        ('applicant', 'Lid. de Proyecto'),
        ('final_recommendation', 'Compras'),
        ('purchase_committee', 'Comite de Compras'),
    ], string='Equipo', readonly=True)
    state = fields.Selection([
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('recommended', 'Recomendado'),
        ('not_recommended', 'No Recomendado')
    ], string='Estado', readonly=True)
    """CHAR"""
    observation = fields.Char(string='Observación', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(PurchaseProjectObservationRecommendation, self).create(vals_list)
        for record in records:
            if record.quotation_id:
                record.quotation_id._notify_timeline_update(reason="observation_create")
        return records


class PurchaseManagementQuotationObservation(models.Model):
    _name = 'purchase.management.quotation.observation'
    _description = 'Observaciones de cotización'

    """MANY2ONE"""
    quotation_id = fields.Many2one(
        'quotation.quotation', string='Cotización', readonly=True, ondelete='cascade')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.onchange('name')
    def _onchange_name(self):
        for record in self:
            if record.name:
                record.name = convert_first_letter_to_uppercase(
                    record.name)
