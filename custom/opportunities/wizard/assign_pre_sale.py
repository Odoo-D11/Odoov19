
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from markupsafe import Markup


class CrmAssignPreSaleLine(models.TransientModel):
    _name = 'opportunity.assign.pre.sale.line'
    _description = 'Línea de asignación de preventa'

    """MANY2ONE"""
    member_id = fields.Many2one(
        'opportunity.team.member', string='Integrante', required=True, domain="[('team_id.name', '=', 'Preventa')]")
    percentage_id = fields.Many2one(
        'opportunity.percentage', string='Porcentaje', required=True)
    role_id = fields.Many2one(
        'opportunity.role', string='Rol', required=True)
    opportunity_assign_pre_sale_id = fields.Many2one(
        'opportunity.assign.pre.sale', string='Asignar preventa', required=True, ondelete='cascade')


class CrmAssignPreSale(models.TransientModel):
    _name = 'opportunity.assign.pre.sale'
    _description = 'Asignar preventa'

    """ONE2MANY"""
    line_ids = fields.One2many(
        'opportunity.assign.pre.sale.line', 'opportunity_assign_pre_sale_id', string='Líneas de asignación', )
    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)

    def assign_pre_sale(self):
        self.ensure_one()
        lead_id = self.env['opportunity'].browse(self.lead_id.id)
        if not lead_id:
            raise ValidationError(
                _("La oportunidad no se ha encontrado, cierra la ventana y vuelve a intentarlo. "
                  "Si el problema persiste, contacta con el administrador del sistema."))
        for member in self.line_ids:
            with self.env.cr.savepoint():
                self = self.with_context(skip_check=True)
            assignment = self.env['opportunity.team.assignment'].sudo().create({
                'member_id': member.member_id.id,
                'lead_id': self.lead_id.id,
            })
            self.env['opportunity.team.assignment.line'].sudo().create({
                'assignment_id': assignment.id,
                'team_id': member.member_id.team_id.id,
                'role_id': member.role_id.id,
                'member_id': member.member_id.id,
                'percentage_id': member.percentage_id.id,
            })
        member_names = ', '.join(
            member.employee_id.name for member in self.line_ids.mapped('member_id'))
        dest_text = "al <span style='color: #017e84;'>estudio de mercado</span>" if self.lead_id.type_opportunity_id.name in [
            'Estudio de mercado', 'RFI'] else "a la <span style='color: #017e84;'>oportunidad</span>"
        user_text = " El usuario asignado es: " if len(
            self.line_ids) == 1 else " A continuación, se detalla la lista de usuarios asignados: "
        msg = Markup(
            f"<span>Se realizado la <span style='color: #017e84;'>asignación de el equipo de preventa</span> {dest_text}."
            f"{user_text}"
            f"<span style='color: #017e84;'>{member_names}</span>.</span>"
        )
        lead_id.sudo().message_post(body=msg)
        lead_id.sudo().write({
            'assigned_pre_sales': True,
            'stage': 'pte_upload_offer' if lead_id.type in ['study', 'pipeline'] else lead_id.stage,
            'stage_pre_sale': 'in_management',
        })
        template = self.env.ref(
            'opportunities.email_template_pre_sale_assignment')
        if template:
            for line in self.line_ids:
                template.sudo().with_context(employee_name=line.member_id.employee_id.name).send_mail(self.lead_id.id, email_values={
                    'email_to': line.member_id.employee_id.work_email,
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
                [('lead_id', '=', lead_id.id), ('state', '=', 'Esperando asignación equipo de preventa')], limit=1)
            raw_html = (
                "<span style='color: #017e84;'>Esperando MVF - Valoración financiera...</span>"
                if lead_id.type == 'opportunity'
                else "<span style='color: #017e84;'>Esperando cargue de oferta...</span>"
            )
            description = str(Markup(raw_html))
            state = 'Esperando MVF - Valoración financiera' if lead_id.type == 'opportunity' else 'Esperando cargue de oferta'
            if assign:
                assign.sudo().write({
                    'description': msg,
                    'state': 'Equipo de preventa asignado',
                    'end_date': fields.Datetime.now(),
                })
                self.env['opportunity.timesheet'].sudo().create({
                    'lead_id': lead_id.id,
                    'member_id': member.id,
                    'description': description,
                    'state': state,
                    'start_date': lead_id.create_date,
                })
