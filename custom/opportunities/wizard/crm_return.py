
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase


class CrmReturn(models.TransientModel):
    _name = 'opportunity.return'
    _description = 'Devolver oportunidad'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    reason_id = fields.Many2one(
        'opportunity.reason', string='Motivo', required=True, domain="[('name', '=', 'No viable')]")
    """TEXT"""
    observation = fields.Text(string='Observación', required=True)

    @api.model
    def default_get(self, fields):
        defaults = super(CrmReturn, self).default_get(fields)
        reason = self.env['opportunity.reason'].search(
            [('name', '=', 'No viable')], limit=1)
        if not reason:
            raise UserError(
                _("No se ha encontrado el motivo 'No viable'. "
                  "Por favor, contacta con el administrador del sistema."))
        defaults['reason_id'] = reason.id
        return defaults

    def return_lead(self):
        self.ensure_one()
        lead_id = self.env['opportunity'].browse(self.lead_id.id)
        if not lead_id:
            raise ValidationError(
                _("La oportunidad no se ha encontrado, cierra la ventana y vuelve a intentarlo. "
                  "Si el problema persiste, contacta con el administrador del sistema."))
        observation = convert_first_letter_to_uppercase(self.observation)
        self.lead_id.sudo().write({'stage': 'open'})
        msg = Markup(
            f"<span>El registro ha sido <span style='color: #017e84;'>devuelto a comercial</span> debido al siguiente motivo: "
            f"<span style='color: #017e84;'>{self.reason_id.name}</span>. "
            f"A continuación, se proporciona <span style='color: #017e84;'>una observación</span> detallada para su revisión y seguimiento: "
            f"<span style='color: #017e84;'>{observation}</span>. "
            f"Se recomienda evaluar esta información y <span style='color: #017e84;'>verificar si es posible continuar con el proceso.</span> </span>"
        )
        template = self.env.ref(
            'opportunities.email_template_opportunity_return')
        if template:
            template.sudo().with_context(reason=self.observation).send_mail(
                self.lead_id.id, email_values={'email_to': self.lead_id.create_uid.email})
        self.env['opportunity.history'].sudo().create({
            'lead_id': self.lead_id.id,
            'member_id': self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.uid)], limit=1).id,
            'reason_id': self.reason_id.id,
            'description': observation,
        })
        # Tiempos (opportunity.timesheet)
        if len(self.lead_id.timesheet_ids) > 0:
            member = self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.uid)], limit=1)
            if not member:
                raise UserError(
                    "No se ha encontrado el miembro del equipo de oportunidades. "
                    "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
        state_mapping = {
            False: 'Esperando asignación equipo de preventa',
            'opportunity': 'Esperando MVF - Valoración financiera',
            'study': 'Esperando cargue de oferta',
            'pipeline': 'Esperando cargue de oferta'
        }
        state = state_mapping.get(
            self.lead_id.type if self.lead_id.assigned_pre_sales else False)
        assign = self.env['opportunity.timesheet'].search(
            [('lead_id', '=', self.lead_id.id), ('state', '=', state)], limit=1)
        if assign:
            assign.sudo().write({
                'description': msg,
                'state': 'Devuelto a comercial',
                'end_date': fields.Datetime.now(),
            })
            self.env['opportunity.timesheet'].sudo().create({
                'lead_id': self.lead_id.id,
                'member_id': member.id,
                'description': Markup(
                    f"<span style='color: #017e84;'>Esperando respuesta de comercial...</span>"
                ),
                'state': 'Esperando respuesta de comercial',
                'start_date': fields.Datetime.now(),
            })
        lead_id.sudo().message_post(body=msg)
