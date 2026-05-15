
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FinancialAssessmentLine(models.Model):
    _name = 'financial.assessment.line'
    _description = 'Línea de valoración financiera'
    _rec_name = 'financial_costs_id'

    """MANY2ONE"""
    assessment_id = fields.Many2one(
        'financial.assessment', string='Valoración financiera')
    financial_costs_id = fields.Many2one(
        'financial.cost', string='Costos financieros', required=True, readonly=True)
    """FLOAT"""
    percentage = fields.Float(string='Porcentaje')
    """INTEGER"""
    total = fields.Float(string='Total', digits=(16, 0))


class FinancialAssessment(models.Model):
    _name = 'financial.assessment'
    _description = 'Valoración financiera'
    _rec_name = 'lead_id'

    """ONE2MANY"""
    assessment_line_ids = fields.One2many(
        'financial.assessment.line', 'assessment_id', string='Líneas')
    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', ondelete='cascade',  readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', readonly=True,)
    """HTML"""
    assessment = fields.Html(string='Valoración', readonly=True)
    """CHAR"""
    link = fields.Char(string='Enlace', readonly=True)

    def action_view_history(self):
        self.ensure_one()
        if self.env['history.financial.assessment'].search_count([('lead_id', '=', self.lead_id.id)]) > 0:
            return {
                'name': _('Historial'),
                'type': 'ir.actions.act_window',
                'res_model': 'history.financial.assessment',
                'view_mode': 'list,form',
                'target': 'current',
                'domain': [('lead_id', '=', self.lead_id.id)],
            }
        else:
            raise ValidationError(_(
                "No se ha encontrado historial de valoraciones financieras para este registro."))

    def action_open_link(self):
        self.ensure_one()
        if self.link and self.link.startswith(('http://', 'https://')):
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_url',
                'url': self.link,
                'target': 'new',
            }
        else:
            raise ValidationError(
                "El enlace de la valoración financiera no es válido. Por favor, comuníquese con el administrador del sistema.")


class HistoryFinancialAssessment(models.Model):
    _name = 'history.financial.assessment'
    _description = 'Historial MVF'
    _rec_name = 'lead_id'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', ondelete='cascade', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', readonly=True,)
    """HTML"""
    assessment = fields.Html(string='Valoración', readonly=True)
    """INTEGER"""
    version = fields.Integer(string='Versión', readonly=True)
    """CHAR"""
    link = fields.Char(string='Link', readonly=True)
