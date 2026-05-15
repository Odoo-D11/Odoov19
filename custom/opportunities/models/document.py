
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from markupsafe import Markup


class OpportunityTypeDocument(models.Model):
    _name = 'opportunity.type.document'
    _description = 'Tipo de documento'

    """ONE2MANY"""
    document_ids = fields.One2many(
        'opportunity.document', 'type_document_id', string='Documentos')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Calificación", "MVF - Valoración Financiera",
                          "Oferta"]

        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})


class OpportunityDocument(models.Model):
    _name = 'opportunity.document'
    _description = 'Documento'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', ondelete='cascade', index=True)
    type_document_id = fields.Many2one(
        'opportunity.type.document', string='Tipo de documento', required=True)
    """SELECTION"""
    document = fields.Selection(
        [('mvf', 'MVF'),
         ('qualification', 'Calificación'),
         ('offer', 'Oferta')],
        string='Documento', compute='_compute_document', store=True)
    """CHAR"""
    link = fields.Char(string='Enlace', required=True)
    """HTML"""
    resume = fields.Html(
        string='Resumen', compute='_compute_resume')

    @api.depends('link')
    def _compute_resume(self):
        for rec in self:
            if rec.link:
                if rec.link.startswith(('http://', 'https://')):
                    rec.resume = Markup(
                        f'<span>{rec.type_document_id.name}</span>')
                else:
                    rec.resume = Markup(
                        f'<span>{rec.type_document_id.name} - <span class="text-danger">{rec.link}</span></span>')
            else:
                rec.resume = False

    @api.depends('type_document_id')
    def _compute_document(self):
        for rec in self:
            if rec.type_document_id.name == 'MVF - Valoración Financiera':
                rec.document = 'mvf'
            elif rec.type_document_id.name == 'Calificación':
                rec.document = 'qualification'
            elif rec.type_document_id.name == 'Oferta':
                rec.document = 'offer'
            else:
                rec.document = False

    def action_open_document(self):
        self.ensure_one()
        if self.link and self.link.startswith(('http://', 'https://')):
            if self.type_document_id.name == 'MVF - Valoración Financiera':
                assessment = len(self.lead_id.assessment_ids)
                if assessment == 0:
                    return {
                        'type': 'ir.actions.act_url',
                        'url': self.link,
                        'target': 'new',
                    }
                elif assessment > 0:
                    return {
                        'name': _('Odoo'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'financial.assessment',
                        'view_mode': 'form',
                        'res_id': self.lead_id.assessment_ids.id,
                        'target': 'new',
                    }
            elif self.type_document_id.name == 'Calificación':
                return {
                    'type': 'ir.actions.act_url',
                    'url': self.link,
                    'target': 'new',
                }
            elif self.type_document_id.name == 'Oferta':
                return {
                    'type': 'ir.actions.act_url',
                    'url': self.link,
                    'target': 'new',
                }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _(
                        'No se puede abrir el documento seleccionado debido a que no se agregó una URL válida.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
