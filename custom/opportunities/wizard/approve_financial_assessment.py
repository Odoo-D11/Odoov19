
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
from bs4 import BeautifulSoup
from ..utils.utils import convert_first_letter_to_uppercase, get_financial_costs, get_cost_values, calculate_financial_data, edit_financial_values


class ApproveFinancialAssessment(models.TransientModel):
    _name = 'approve.financial.assessment'
    _description = 'Aprobar valoración financiera'

    """ONE2MANY"""
    edit_financial_costs_ids = fields.One2many(
        'edit.financial.assessment.line', 'approve_id', string='Costos financieros')
    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    """HTML"""
    assessment = fields.Html(
        string='Valoración financiera', readonly=True)
    """SELECTION"""
    rta = fields.Selection(
        [('si', 'Sí'), ('no', 'No')], string='Respuesta', )
    """TEXT"""
    observations = fields.Text(string='Observaciones')
    """BOOLEAN"""
    next_step = fields.Boolean(
        string='¿Desea continuar con el siguiente paso?', default=False, readonly=True)
    edit_financial_costs = fields.Boolean(
        string='Editar los costos financieros', default=False, readonly=True)

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
        if not self.next_step:
            self.next_step = True
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'approve.financial.assessment',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        else:
            self.next_step = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'approve.financial.assessment',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }

    def action_edit_financial_costs(self):
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
        # Obtenemos los porcentajes de los costos financieros HTML
        values = edit_financial_values(
            self.assessment)
        if not values:
            raise ValidationError(_(
                "No se encontraron costos financieros para editar. "
                "Esto puede deberse a que no hay costos financieros asociados a la oportunidad o que los datos "
                "no están disponibles en el formato esperado.\n\n"
                "Para solucionar este problema:\n"
                "- Comunique con el administrador del sistema para verificar la configuración de los costos financieros.\n"
            ))
        if not self.edit_financial_costs:
            self.edit_financial_costs = True
            if not self.edit_financial_costs_ids:
                for cost in values.keys():
                    financial_costs = self.env['financial.cost'].search([
                        ('name', 'ilike', cost)], limit=1)
                    if financial_costs:
                        self.edit_financial_costs_ids.create({
                            'approve_id': self.id,
                            'financial_costs_id': financial_costs.id,
                            'percentage': values[cost],
                        })
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'approve.financial.assessment',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        else:
            self.edit_financial_costs = False
            self.edit_financial_costs_ids = [(5, 0, 0)]
            vf = self.env['financial.assessment'].search(
                [('lead_id', '=', self.lead_id.id)], limit=1)
            if not vf:
                raise ValidationError(_(
                    "No se encontró la valoración financiera asociada a la oportunidad. "
                    "Esto puede deberse a que no hay valoración financiera registrada o que los datos "
                    "no están disponibles en el formato esperado.\n\n"
                    "Para solucionar este problema:\n"
                    "- Comunique con el administrador del sistema para verificar la configuración de la valoración financiera.\n"
                ))
            self.assessment = vf.assessment
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'approve.financial.assessment',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }

    def action_save_financial_costs(self):
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
        financial_costs = self.edit_financial_costs_ids.mapped(
            'financial_costs_id')
        percentages = self.edit_financial_costs_ids.mapped(
            'percentage')
        cost_values = {cost.name: percentage for cost,
                       percentage in zip(financial_costs, percentages)}
        soup = BeautifulSoup(self.assessment, 'html.parser')
        tbody = soup.find('tbody', id='financial-body')
        values = {}
        if tbody:
            for tr in tbody.find_all('tr'):
                cell_desc = tr.find('td', class_='description')
                cell_value = tr.find('td', class_='valor')
                if cell_desc and cell_value:
                    description = cell_desc.get_text(strip=True)
                    if description in ["Ingresos", "Costos"]:
                        values[description] = cell_value.get_text(strip=True)
        if not values:
            raise ValidationError(_(
                "No se encontraron valores de ingresos o costos. "
                "Esto puede deberse a que los datos no están disponibles en el formato esperado.\n\n"
                "Para solucionar este problema:\n"
                "- Comunique con el administrador del sistema para verificar la configuración de los costos financieros.\n"
            ))
        income = int(values.get("Ingresos").replace(
            "$", "").replace(".", "").replace(",", ""))
        cost = int(values.get("Costos").replace(
            "$", "").replace(".", "").replace(",", ""))
        partner_id = self.lead_id.partner_id
        financial_data, percentage_data = calculate_financial_data(
            income, cost, cost_values)
        calculated_data = {
            'financial_data': financial_data,
            'percentage_data': percentage_data,
            'cost_values': cost_values,
        }
        self.assessment = get_financial_costs(
            self.env, partner_id, income, cost, None, calculated_data)
        self.edit_financial_costs = False
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'approve.financial.assessment',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_approve(self):
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
                "Debe seleccionar una respuesta antes de continuar. "
                "Por favor, seleccione una respuesta y vuelva a intentarlo."
            ))
        if not self.observations:
            raise ValidationError(_(
                "Debe ingresar una observación antes de continuar. "
                "Por favor, ingrese una observación y vuelva a intentarlo."
            ))
        if self.lead_id.stage in ['pte_approval_pre_sale_leader', 'pte_approval_manager']:
            stages = {
                'pte_approval_pre_sale_leader': {
                    'si': 'pte_approval_manager',
                    'no': 'in_pre_sale',
                    'role': '<span style="color: #017e84;">líder de preventa</span>'
                },
                'pte_approval_manager': {
                    'si': 'pte_upload_offer',
                    'no': 'in_pre_sale',
                    'role': '<span style="color: #017e84;">área financiera</span>'
                }
            }
            role = stages[self.lead_id.stage]['role']
            next_stage = stages[self.lead_id.stage].get(self.rta)
            observations = convert_first_letter_to_uppercase(self.observations)
            if next_stage:
                if len(self.lead_id.timesheet_ids) > 0:
                # Tiempos (opportunity.timesheet)
                    member = self.env['opportunity.team.member'].search(
                        [('employee_id.user_id', '=', self.env.uid)], limit=1)
                    if not member:
                        raise ValidationError(
                            "No se ha encontrado el miembro del equipo de oportunidades. "
                            "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
                state = 'Esperando aprobación MVF - Valoración financiera, enviado al líder de preventa' if self.lead_id.stage == 'pte_approval_pre_sale_leader' else 'Esperando aprobación MVF - Valoración financiera, enviado al área financiera'
                # print("state", state)
                approve = self.env['opportunity.timesheet'].search(
                    [('lead_id', '=', self.lead_id.id),
                     ('state', '=', state)], limit=1)
                if self.rta == 'si':
                    msg = Markup(
                        f"<span>La <span style='color: #017e84;'>valoración financiera</span> fue aprobada por el {role} "
                        f"después de un análisis detallado de los criterios establecidos. La aprobación se otorga "
                        f"con base en la siguiente observación: <span style='color: #017e84;'>{observations}</span></span>. "
                    )
                    if approve:
                        approve.sudo().write({
                            'description': msg,
                            'state': f"Aprobación {Markup(role).striptags()} - MVF",
                            'end_date': fields.Datetime.now(),
                        })
                        if self.lead_id.stage == 'pte_approval_pre_sale_leader':
                            self.env['opportunity.timesheet'].sudo().create({
                                'lead_id': self.lead_id.id,
                                'member_id': member.id,
                                'description': Markup(
                                    f"<span style='color: #017e84;'>Esperando aprobación MVF - Valoración financiera del área financiera...</span>"
                                ),
                                'state': 'Esperando aprobación MVF - Valoración financiera, enviado al área financiera',
                                'start_date': fields.Datetime.now(),
                            })
                        elif self.lead_id.stage == 'pte_approval_manager':
                            self.env['opportunity.timesheet'].sudo().create({
                                'lead_id': self.lead_id.id,
                                'member_id': member.id,
                                'description': Markup(
                                    f"<span style='color: #017e84;'>Esperando cargue de oferta...</span>"
                                ),
                                'state': 'Esperando cargue de oferta',
                                'start_date': fields.Datetime.now(),
                            })
                else:
                    msg = Markup(
                        f"<span>La <span style='color: #017e84;'>valoración financiera</span> no cumple con los criterios exigidos para continuar "
                        f"y ha sido rechazada por el {role}. La decisión se fundamenta en la siguiente observación: "
                        f"<span style='color: #017e84;'>{observations}</span>. </span>"
                    )
                    if approve:
                        approve.sudo().write({
                            'description': msg,
                            'state': f"Rechazo {Markup(role).striptags()} - MVF",
                            'end_date': fields.Datetime.now(),
                        })
                        self.env['opportunity.timesheet'].sudo().create({
                            'lead_id': self.lead_id.id,
                            'member_id': member.id,
                            'description': Markup(
                                f"<span style='color: #017e84;'>Esperando MVF - Valoración financiera...</span>"
                            ),
                            'state': 'Esperando MVF - Valoración financiera',
                            'start_date': fields.Datetime.now(),
                        })
                    
                self.lead_id.sudo().write({
                    'stage': next_stage,
                    'stage_pre_sale': 'in_management' if self.rta == 'no' else self.lead_id.stage_pre_sale,
                })
                self.lead_id.sudo().message_post(body=msg)
