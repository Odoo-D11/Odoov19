
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from markupsafe import Markup


class ConvertPipelineTo(models.TransientModel):
    _name = 'opportunity.pipeline.to'
    _description = 'Convertir pipeline a'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True)
    """SELECTION"""
    type = fields.Selection([
        ('study', 'Estudio de mercado'),
        ('lead', 'Oportunidad'),
    ], string='Tipo')

    def action_convert(self):
        self.ensure_one()
        if not self.lead_id:
            raise ValidationError(_(
                "No se ha encontrado la oportunidad vinculada. "
                "Esto puede deberse a que la ventana emergente se ha abierto de forma incorrecta o que la oportunidad "
                "se ha eliminado o modificado antes de completar la operación.\n\n"
                "Para solucionar este problema:\n"
                "- Cierre esta ventana y vuelva a intentarlo.\n"
                "- Asegúrese de que la oportunidad aún existe y está activa.\n"
                "- Si el problema persiste, contacte con el administrador del sistema para revisar posibles "
                "errores en la base de datos o configuración."
            ))
        if not self.type:
            raise ValidationError(_(
                "Debe seleccionar un tipo para continuar con la operación. "
                "Por favor, seleccione una de las opciones disponibles y vuelva a intentarlo."
            ))
        if not self.lead_id.category_id:
            raise ValidationError(_(
                "No se ha encontrado la categoria vinculada al registro. "
                "Esto puede deberse a que el registro no tiene una categoria asignada o que la categoria "
                "se ha eliminado o modificado antes de completar la operación.\n\n"
                "Para solucionar este problema:\n"
                "- Cierre esta ventana y vuelva a intentarlo.\n"
                "- Asegúrese de que la categoria aún existe y está activa.\n"
                "- Si el problema persiste, contacte con el administrador del sistema para revisar posibles "
            ))
        if self.type == 'study':
            # Crear estudio de mercado
            if self.lead_id.sector_id.name == 'Público':
                publi_edm = self.env['opportunity'].sudo().create({
                    'name': self.lead_id.name,
                    'partner_id': self.lead_id.partner_id.id,
                    'sector_id': self.lead_id.sector_id.id,
                    'type_opportunity_id': self.env['opportunity.type'].search([('name', '=', 'Estudio de mercado')], limit=1).id,
                    'reference': self.env['ir.sequence'].next_by_code('opportunity.edm'),
                    'enterprise_id': self.lead_id.enterprise_id.id,
                    'description': self.lead_id.description,
                    'stage': 'draft',
                    'lead_id': self.lead_id.id,
                    'type': 'study',
                    'category_id': self.lead_id.category_id.id,                   
                })
            elif self.lead_id.sector_id.name == 'Privado':
                priv_edm = self.env['opportunity'].sudo().create({
                    'name': self.lead_id.name,
                    'partner_id': self.lead_id.partner_id.id,
                    'sector_id': self.lead_id.sector_id.id,
                    'enterprise_id': self.lead_id.enterprise_id.id,
                    'description': self.lead_id.description,
                    'type_opportunity_id': self.env['opportunity.type'].search([('name', '=', 'RFI')], limit=1).id,
                    'reference': self.env['ir.sequence'].next_by_code('opportunity.edm'),
                    'stage': 'draft',
                    'lead_id': self.lead_id.id,
                    'type': 'study',
                    'category_id': self.lead_id.category_id.id,
                })
            type = publi_edm if self.lead_id.sector_id.name == 'Público' else priv_edm
            msg = Markup(
                'Se ha creado un <span style="color: #017e84;">estudio de mercado</span> a partir de este registro. La referencia del nuevo estudio es <a style="color: #017e84;" href="#id=%s&action=0" data-oe-model=opportunity data-oe-id=%s>%s</a>.' % (
                    type.id, type.id, type.reference))
            self.lead_id.sudo().message_post(body=msg)
            activities = self.env['opportunity.activity'].search(
                [('lead_id', '=', self.lead_id.id)])
            for activity in activities:
                activity.message_post(body=msg)
            return {
                'name': _('Nueva'),
                'view_mode': 'form',
                'res_model': 'opportunity',
                'res_id': type.id,
                'type': 'ir.actions.act_window',
            }
        elif self.type == 'lead':
            # Crear oportunidad
            if self.lead_id.sector_id.name == 'Privado':
                priv_opp = self.env['opportunity'].sudo().create({
                    'name': self.lead_id.name,
                    'partner_id': self.lead_id.partner_id.id,
                    'sector_id': self.lead_id.sector_id.id,
                    'type_opportunity_id': self.env['opportunity.type'].search([('name', '=', 'RFP')], limit=1).id,
                    'reference': self.env['ir.sequence'].next_by_code('opportunity'),
                    'enterprise_id': self.lead_id.enterprise_id.id,
                    'description': self.lead_id.description,
                    'stage': 'draft',
                    'lead_id': self.lead_id.id,
                    'type': 'opportunity',
                    'category_id': self.lead_id.category_id.id,
                })
            elif self.lead_id.sector_id.name == 'Público':
                public_opp = self.env['opportunity'].sudo().create({
                    'name': self.lead_id.name,
                    'partner_id': self.lead_id.partner_id.id,
                    'sector_id': self.lead_id.sector_id.id,
                    'reference': self.env['ir.sequence'].next_by_code('opportunity'),
                    'description': self.lead_id.description,
                    'enterprise_id': self.lead_id.enterprise_id.id,
                    'stage': 'draft',
                    'lead_id': self.lead_id.id,
                    'type': 'opportunity',
                    'category_id': self.lead_id.category_id.id,
                })
            type = public_opp if self.lead_id.sector_id.name == 'Público' else priv_opp
            msg = Markup(
                'Se ha creado una <span style="color: #017e84;">oportunidad</span> a partir de este registro. La referencia de la nueva oportunidad es <a style="color: #017e84;" href="#id=%s&action=0" data-oe-model=opportunity data-oe-id=%s>%s</a>.' % (
                    type.id, type.id, type.reference))
            self.lead_id.sudo().message_post(body=msg)
            activities = self.env['opportunity.activity'].search(
                [('lead_id', '=', self.lead_id.id)])
            for activity in activities:
                activity.message_post(body=msg)
            return {
                'name': _('Nueva'),
                'view_mode': 'form',
                'res_model': 'opportunity',
                'res_id': type.id,
                'type': 'ir.actions.act_window',
            }
        self.lead_id.active = False
