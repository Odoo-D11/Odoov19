
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
from ..utils.utils import is_html_content_empty, format_html_to_sentence_case


class CrmWon(models.TransientModel):
    _name = 'opportunity.won'
    _description = 'Ganar oportunidad'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    reason_id = fields.Many2one(
        'opportunity.reason', string='Motivo',)
    """HTML"""
    observation = fields.Html(string='Observación',)
    """SELECTION"""
    rta = fields.Selection(
        [('yes', 'Si'), ('no', 'No')], string='Respuesta')
    """BOOLEAN"""
    next_step = fields.Boolean(
        string='Siguiente paso', readonly=True, default=False)

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
                'res_model': 'opportunity.won',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        else:
            self.next_step = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'opportunity.won',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }

    def action_set_won(self):
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
        if not self.reason_id:
            raise ValidationError(_(
                "Debe seleccionar un motivo para continuar con la operación. "
                "Por favor, seleccione uno de los motivos disponibles y vuelva a intentarlo."
            ))
        if is_html_content_empty(self.observation) and self.rta == 'no':
            raise ValidationError(_(
                "Debe ingresar una observación para continuar con la operación. "
                "Por favor, ingrese el motivo por el cual la oportunidad no se ha ganado y vuelva a intentarlo."
            ))
        self.lead_id.sudo().write({
            'active': False,
            'stage': 'lost' if self.rta == 'no' else 'won',
        })
        observation = format_html_to_sentence_case(self.observation)
        if self.rta == 'no':
            extra = f"<span>El motivo registrado es <span style='color: #017e84;'>{self.reason_id.name}</span> y se ha documentado la siguiente observación: <span style='color: #017e84;'>{observation}</span>.</span>"
        else:
            extra = ''
        msg = Markup(
            f"<span>Se ha "
            f"marcado como <span style='color: #017e84;'>{'Ganada' if self.rta == 'yes' else 'Perdida'}</span>. </span> "
            f"{extra}"
        )
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
                raise UserError(
                    "No se ha encontrado el miembro del equipo de oportunidades. "
                    "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
        assign = self.env['opportunity.timesheet'].search(
            [('lead_id', '=', self.lead_id.id), ('state', '=', 'Esperando cierre de la oportunidad')], limit=1)
        if assign:
            assign.sudo().write({
                'description': msg,
                'state': 'Oportunidad cerrada',
                'end_date': fields.Datetime.now(),
            })
        self.lead_id.sudo().message_post(body=msg)
