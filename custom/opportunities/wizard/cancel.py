
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase


class CrmCancel(models.TransientModel):
    _name = 'opportunity.cancel'
    _description = 'Cancelar oportunidad'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    reason_id = fields.Many2one(
        'opportunity.reason', string='Motivo', required=True)
    """TEXT"""
    observation = fields.Text(string='Observación', required=True)

    def action_cancel(self):
        self.ensure_one()
        lead_id = self.env['opportunity'].browse(self.lead_id.id)
        if not lead_id:
            raise ValidationError(
                _("La oportunidad no se ha encontrado, cierra la ventana y vuelve a intentarlo. "
                  "Si el problema persiste, contacta con el administrador del sistema."))
        observation = convert_first_letter_to_uppercase(self.observation)
        lead_id.sudo().write(
            {'active': False, 'stage': 'cancelled', 'stage_pre_sale': 'cancelled'})
        msg = Markup(
            "<span>Este proceso ha sido <span class='text-danger'>cancelado</span> por el siguiente motivo <span class='text-danger'>%s</span>. "
            "Además, se ha registrado la siguiente nota: %s.</span>"
            % (self.reason_id.name.lower(), observation)
        )
        self.env['opportunity.history'].sudo().create({
            'lead_id': lead_id.id,
            'member_id': self.env['opportunity.team.member'].search([
                ('employee_id', '=', self.env.user.employee_id.id)], limit=1).id,
            'date': fields.Date.context_today(self),
            'reason_id': self.reason_id.id,
            'description': Markup("<span>%s</span>" % observation)
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
            [('lead_id', '=', lead_id.id), ('end_date', '=', False)], limit=1)
        if assign:
            assign.sudo().write({
                'description': msg,
                'state': 'Oportunidad cerrada',
                'end_date': fields.Datetime.now(),
            })
        lead_id.sudo().message_post(body=msg)
