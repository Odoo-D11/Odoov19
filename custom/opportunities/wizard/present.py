
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
from ..utils.utils import is_html_content_empty, format_html_to_sentence_case


class PresentLead(models.TransientModel):
    _name = 'present.lead'
    _description = 'Presentar oportunidad'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    reason_id = fields.Many2one(
        'opportunity.reason', string='Motivo',)
    """SELECTION"""
    rta = fields.Selection(
        [('yes', 'Sí'), ('no', 'No')], string='Respuesta', )
    """HTML"""
    observation = fields.Html(string='Observaciones')
    """BOOLEAN"""
    next_step = fields.Boolean(
        string='¿Desea continuar con el siguiente paso?', default=False, readonly=True)

    def action_next_step(self):
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
        if not self.rta:
            raise ValidationError(_(
                "Debe seleccionar una respuesta para continuar con la operación. "
                "Por favor, seleccione una de las opciones disponibles y vuelva a intentarlo."
            ))
        if not self.next_step:
            self.next_step = True
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'present.lead',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        else:
            self.next_step = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'present.lead',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }

    def action_present_lead(self):
        if is_html_content_empty(self.observation) and self.rta == 'no':
            raise ValidationError(_(
                "Debe ingresar una observación antes de continuar. "
                "Por favor, complete este campo y vuelva a intentarlo."
            ))
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
        if not self.rta:
            raise ValidationError(_(
                "Debe seleccionar una respuesta para continuar con la operación. "
                "Por favor, seleccione una de las opciones disponibles y vuelva a intentarlo."
            ))
        if self.rta == 'no' and not self.observation or self.reason_id:
            raise ValidationError(_(
                "Verifique que ha ingresado una observación o seleccionado un motivo antes de continuar. "
                "Por favor, complete los campos requeridos y vuelva a intentarlo."
            ))
        self.lead_id.sudo().write({
            'stage': 'presented' if self.rta == 'yes' else 'cancelled',
            'stage_pre_sale': 'cancelled' if self.rta == 'no' else self.lead_id.stage_pre_sale,
            'active': False if self.lead_id.type in ['study', 'pipeline'] else True,
        })
        observation = format_html_to_sentence_case(self.observation)
        status_message = '<span>Se ha marcado como <span style="color: #017e84;">cancelado</span>.' if self.rta == 'no' else '<span>Se ha marcado como <span style="color: #017e84;">presentado</span>.'
        observation_message = f" A continuación, se detalla la observación registrada: <span>{observation}</span>. </span>" if observation else ''
        msg = Markup(f"{status_message}{observation_message}")
        if self.rta == 'no':
            self.env['opportunity.history'].sudo().create({
                'lead_id': self.lead_id.id,
                'member_id': self.env['opportunity.team.member'].search([
                    ('employee_id', '=', self.env.user.employee_id.id)], limit=1).id,
                'date': fields.Date.context_today(self),
                'reason_id': self.reason_id.id,
                'description': Markup("<span>%s</span>" % observation) if observation else False
            })
        # Tiempos (opportunity.timesheet)
        if len(self.lead_id.timesheet_ids) > 0:
            member = self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.uid)], limit=1)
            if not member:
                raise ValidationError(
                    "No se ha encontrado el miembro del equipo de oportunidades. "
                    "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
        assign = self.env['opportunity.timesheet'].search(
            [('lead_id', '=', self.lead_id.id), ('state', '=', 'Esperando a presentar la oferta')], limit=1)
        if assign:
            assign.sudo().write({
                'description': msg,
                'state': 'Oferta presentada',
                'end_date': fields.Datetime.now(),
            })            
            if self.lead_id.type == 'opportunity' and self.rta == 'yes':
                self.env['opportunity.timesheet'].sudo().create({
                    'lead_id': self.lead_id.id,
                    'member_id': member.id,
                    'description': Markup(
                        f"<span style='color: #017e84;'>Esperando cierre de la oportunidad...</span>"
                    ),
                    'state': 'Esperando cierre de la oportunidad',
                    'start_date': fields.Datetime.now(),
                })
        self.lead_id.sudo().message_post(body=msg)
