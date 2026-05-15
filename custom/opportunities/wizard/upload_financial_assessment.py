
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..utils.utils import is_valid_url, get_financial_costs, calculate_financial_data, get_cost_values, edit_financial_values
from markupsafe import Markup


class EditFinancialAssessmentLine(models.TransientModel):
    _name = 'edit.financial.assessment.line'
    _description = 'Editar línea de valoración financiera'
    _rec_name = 'financial_costs_id'
    _order = 'financial_costs_id'

    """MANY2ONE"""
    approve_id = fields.Many2one(
        'approve.financial.assessment', string='Aprobación de MVF')
    assessment_id = fields.Many2one(
        'upload.financial.assessment', string='Valoración financiera')
    financial_costs_id = fields.Many2one(
        'financial.cost', string='Nombre', required=True, readonly=True)
    """FLOAT"""
    percentage = fields.Float(string='Porcentaje')


class UploadFinancialAssessment(models.TransientModel):
    _name = 'upload.financial.assessment'
    _description = 'Cargar valoración financiera'

    """ONE2MANY"""
    edit_financial_assessment_line_ids = fields.One2many(
        'edit.financial.assessment.line', 'assessment_id', string='Líneas')
    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', readonly=True, required=True)
    """FLOAT"""
    income = fields.Float(string='Ingreso', required=True, digits=(16, 0))
    cost = fields.Float(string='Costo', required=True, digits=(16, 0))
    """CHAR"""
    link = fields.Char(string='Link', )
    """HTML"""
    financial_assessment = fields.Html(
        string='Valoración financiera', readonly=True)
    """BOOLEAN"""
    preview = fields.Boolean(string='Vista previa',
                             default=False, readonly=True)
    attach_link = fields.Boolean(
        string='Adjuntar link', default=False, readonly=True)
    edit_financial_costs = fields.Boolean(
        string='Editar costos financieros', default=False, readonly=True)

    def action_preview_financial_assessment(self):
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
        if not self.partner_id:
            raise ValidationError(_(
                "No se ha encontrado el cliente asociado. "
                "Esto puede deberse a que la ventana emergente se ha abierto de forma incorrecta o que el cliente "
                "se ha eliminado o modificado antes de completar la operación.\n\n"
                "Para solucionar este problema:\n"
                "- Cierre esta ventana y vuelva a intentarlo.\n"
                "- Asegúrese de que el cliente aún existe y está activo.\n"
                "- Si el problema persiste, contacte con el administrador del sistema para revisar posibles "
                "errores en la base de datos o configuración."
            ))
        if self.income <= 0:
            raise ValidationError(_(
                "El valor del ingreso es inválido. Se requiere un número mayor a cero.\n\n"
                "Este campo debe contener un monto positivo, ya que representa los ingresos proyectados o reales "
                "de la oportunidad.\n\n"
                "Para solucionar este problema:\n"
                "- Verifique que ha ingresado correctamente el monto esperado.\n"
                "- Si se trata de un error tipográfico, corrija el valor y vuelva a intentarlo."
            ))
        if self.cost <= 0:
            raise ValidationError(_(
                "El valor del costo es inválido. Se requiere un número mayor a cero.\n\n"
                "Este campo representa los costos asociados a la oportunidad, por lo que debe ser un número positivo.\n\n"
                "Para solucionar este problema:\n"
                "- Asegúrese de que el costo ingresado es correcto y refleja los gastos reales.\n"
                "- Revise los documentos financieros o proyecciones para asegurarse de que los valores sean precisos."
            ))
        if not self.preview:
            self.preview = True
            self.financial_assessment = get_financial_costs(
                self.env, self.partner_id, self.income, self.cost)
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.financial.assessment',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            self.preview = False
            self.financial_assessment = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.financial.assessment',
                'view_mode': 'form',
                'target': 'new',
                'res_id': self.id,
            }

    def action_attach_link_financial_assessment(self):
        if not self.attach_link:
            self.attach_link = True
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.financial.assessment',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            self.attach_link = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.financial.assessment',
                'view_mode': 'form',
                'target': 'new',
                'res_id': self.id,
            }

    def action_upload_financial_assessment(self):
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
        elif not is_valid_url(self.link):
            raise ValidationError(
                "El enlace ingresado no es válido. Debe comenzar con 'http://', 'https://', o 'ftp://', "
                "contener un dominio válido como 'example.com' o una dirección IP correctamente escrita como '192.168.1.1'. "
                "No debe incluir espacios ni caracteres no permitidos y, si contiene parámetros o rutas, "
                "deben estar bien formateados. Ej. de URLs válidas: https://www.google.com, "
                "http://miempresa.com/contacto, ftp://servidor-archivos.com. Corrige la URL e inténtalo nuevamente."
            )
        """ VERIFICAR SI YA EXISTE UNA VALORACIÓN FINANCIERA """
        assessment = self.env['financial.assessment'].search(
            [('lead_id', '=', self.lead_id.id)]
        )
        """ OBTENER CUÁNTAS VERSIONES HAY EN EL HISTORIAL """
        existing_versions = self.env['history.financial.assessment'].search_count(
            [('lead_id', '=', self.lead_id.id)]
        )
        """ SI YA HAY 3 VERSIONES, IMPEDIR QUE SE CREE UNA NUEVA """
        if existing_versions >= 3:
            raise ValidationError(
                "No se pueden almacenar más de 3 versiones en el historial de valoraciones financieras. "
                "No es posible eliminar versiones antiguas para agregar nuevas. "
                "Por favor, contacte con el administrador del sistema para obtener más información."
            )
        """ SI EXISTE UNA VALORACIÓN Y ESTÁ EN 'presented', GUARDARLA EN EL HISTORIAL """
        if assessment:
            if self.lead_id.stage == 'presented':
                self.env['history.financial.assessment'].sudo().create({
                    'lead_id': assessment.lead_id.id,
                    'partner_id': assessment.partner_id.id,
                    'assessment': assessment.assessment,  # Guardar el HTML antiguo
                    'link': assessment.link,
                    # Asignar versión (1, 2 o 3)
                    'version': existing_versions + 1
                })
            assessment.sudo().unlink()  # Eliminar la valoración financiera existente
        """ CREAR NUEVA VALORACIÓN FINANCIERA """
        self.env['financial.assessment'].sudo().create({
            'lead_id': self.lead_id.id,
            'partner_id': self.partner_id.id,
            'link': self.link,
            'assessment': self.financial_assessment,
        })
        """ MENSAJE EN EL CHAT DE LA OPORTUNIDAD """
        if self.lead_id.stage != 'presented':
            msg = Markup(
                _("Se cargo una nueva valoración financiera para la oportunidad. "
                  "Puede ver el documento dando clic <a style='color: #017e84;' href='%s' target='_blank'>aquí</a>.") % self.link
            )
        else:
            msg = Markup(
                _("Se actualizo la valoración financiera de la oportunidad. "
                  "Puede ver el documento dando clic <a style='color: #017e84;' href='%s' target='_blank'>aquí</a>.") % self.link
            )
        self.lead_id.sudo().message_post(body=msg)
        """ GESTIONAR DOCUMENTO ASOCIADO A LA OPORTUNIDAD """
        document_type = self.env['opportunity.type.document'].search(
            [('name', '=', 'MVF - Valoración Financiera')], limit=1
        )
        existing_document = self.lead_id.document_ids.filtered(
            lambda d: d.type_document_id == document_type
        )
        if existing_document:
            existing_document.sudo().write({'link': self.link})
        else:
            self.lead_id.sudo().write({
                'document_ids': [(0, 0, {
                    'type_document_id': document_type.id,
                    'link': self.link
                })]
            })
        template = self.env.ref(
            'opportunities.email_template_mvf_financial_assessment')
        if template:
            template.sudo().with_context(
                employee_name=self.lead_id.create_uid.name).send_mail(
                    self.lead_id.id,
                email_values={'email_to': self.lead_id.create_uid.email})
        # Tiempos (opportunity.timesheet)
        if len(self.lead_id.timesheet_ids) > 0:
            member = self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.uid)], limit=1)
            if not member:
                raise ValidationError(
                    "No se ha encontrado el miembro del equipo de oportunidades. "
                    "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
        mvf = self.env['opportunity.timesheet'].search(
            [('lead_id', '=', self.lead_id.id), ('state', '=', 'Esperando MVF - Valoración financiera')], limit=1)
        if mvf:
            mvf.sudo().write({
                'description': Markup(
                    f"<span>La valoración financiera para este registro <span style='color: #017e84;'>ha sido cargada exitosamente</span>. "
                    f"Puedes verla dando clic <a style='color: #017e84;' href='{self.link}' target='_blank'>aquí</a>.</span>"
                ),
                'state': 'Valoración financiera cargada',
                'end_date': fields.Datetime.now(),
            })
            self.env['opportunity.timesheet'].sudo().create({
                'lead_id': self.lead_id.id,
                'member_id': member.id,
                'description': Markup(
                    f"<span style='color: #017e84;'>Esperando aprobación de MVF - Valoración financiera, "
                    f"enviado al líder de preventa...</span>"
                ),
                'state': 'Esperando aprobación MVF - Valoración financiera, enviado al líder de preventa',
                'start_date': fields.Datetime.now(),
            })
        """ CAMBIAR ETAPA DE LA OPORTUNIDAD SI APLICA """
        if self.lead_id.stage == 'in_pre_sale':
            self.lead_id.sudo().write(
                {'stage': 'pte_approval_pre_sale_leader',
                 'stage_pre_sale': 'delivered'})

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
        if not self.partner_id:
            raise ValidationError(_(
                "No se ha encontrado el cliente asociado. "
                "Esto puede deberse a que la ventana emergente se ha abierto de forma incorrecta o que el cliente "
                "se ha eliminado o modificado antes de completar la operación.\n\n"
                "Para solucionar este problema:\n"
                "- Cierre esta ventana y vuelva a intentarlo.\n"
                "- Asegúrese de que el cliente aún existe y está activo.\n"
                "- Si el problema persiste, contacte con el administrador del sistema para revisar posibles "
                "errores en la base de datos o configuración."
            ))
        # Obtener los porcentajes de los costos financieros HTML
        values = edit_financial_values(self.financial_assessment)
        if not values:
            raise ValidationError(_(
                "No se encontraron costos financieros para editar. "
                "Esto puede deberse a que la valoración financiera no contiene costos editables o que ya se han "
                "realizado cambios en los costos financieros.\n\n"
                "Para solucionar este problema:\n"
                "- Comunique con el administrador del sistema para verificar la configuración de los costos financieros.\n"
            ))
        if not self.edit_financial_costs:
            self.edit_financial_costs = True
            if not self.edit_financial_assessment_line_ids:
                # Crea las líneas de edición de costos financieros
                for cost in values.keys():
                    financial_cost = self.env['financial.cost'].search(
                        [('name', 'ilike', cost)], limit=1)
                    if financial_cost:
                        self.edit_financial_assessment_line_ids.sudo().create({
                            'assessment_id': self.id,
                            'financial_costs_id': financial_cost.id,
                            'percentage': values[cost],
                        })
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.financial.assessment',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        else:
            self.edit_financial_assessment_line_ids = [(5, 0, 0)]
            self.edit_financial_costs = False
            self.financial_assessment = get_financial_costs(
                self.env, self.partner_id, self.income, self.cost)
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.financial.assessment',
                'view_mode': 'form',
                'target': 'new',
                'res_id': self.id,
            }

    def action_save_edit_financial_costs(self):
        # Obtener los valores de los costos financieros editados
        financial_costs = self.edit_financial_assessment_line_ids.mapped(
            'financial_costs_id')
        percentages = self.edit_financial_assessment_line_ids.mapped(
            'percentage')
        cost_values = {cost.name: percentage for cost,
                       percentage in zip(financial_costs, percentages)}
        # Calcular los nuevos costos financieros y porcentajes
        financial_data, percentage_data = calculate_financial_data(
            self.income, self.cost, cost_values)
        # Preparar los datos calculados para pasarlos a la función
        calculated_data = {
            'financial_data': financial_data,
            'percentage_data': percentage_data,
            'cost_values': cost_values,
        }
        # Actualizar el campo de valoración financiera con los nuevos datos calculados
        self.financial_assessment = get_financial_costs(
            self.env, self.partner_id, self.income, self.cost, None, calculated_data)
        self.edit_financial_costs = False
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'upload.financial.assessment',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }
