
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import ValidationError, UserError
from ..utils.utils import is_valid_url
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase


class CrmUploadDocument(models.TransientModel):
    _name = 'opportunity.upload.document'
    _description = 'Subir documento'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    """CHAR"""
    link = fields.Char(string='Enlace', required=True)
    rating_link = fields.Char(string='Enlace de calificación')
    """SELECTION"""
    rta = fields.Selection(
        [('1', 'Si'), ('2', 'No')], string='Respuesta')
    """TEXT"""
    reason = fields.Text(string='Motivo')
    """BOOLEAN"""
    next_step = fields.Boolean(
        string='¿Siguiente paso?', default=False, readonly=True)

    def action_next_step(self):
        if not is_valid_url(self.link):
            raise ValidationError(
                "El enlace ingresado no es válido. Debe comenzar con 'http://', 'https://', o 'ftp://', "
                "contener un dominio válido como 'example.com' o una dirección IP correctamente escrita como '192.168.1.1'. "
                "No debe incluir espacios ni caracteres no permitidos y, si contiene parámetros o rutas, "
                "deben estar bien formateados. Ej. de URLs válidas: https://www.google.com, "
                "http://miempresa.com/contacto, ftp://servidor-archivos.com. Corrige la URL e inténtalo nuevamente."
            )

        if not self.next_step:
            self.next_step = True
            self.rta = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'opportunity.upload.document',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.id,
                'target': 'new',
                'context': {'default_lead_id': self.lead_id.id}
            }
        else:
            self.next_step = False
            self.rta = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'opportunity.upload.document',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.id,
                'target': 'new',
                'context': {'default_lead_id': self.lead_id.id}
            }

    def return_to_question(self):
        self.rta = False
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'opportunity.upload.document',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'default_lead_id': self.lead_id.id}
        }

    def action_upload_document(self):
        if not self.rta:
            raise ValidationError(
                "El sistema ha detectado que no has seleccionado una respuesta a la pregunta planteada. "
                "Para continuar con el proceso, debes indicar si la URL proporcionada es correcta o no. "
                "Por favor, selecciona una de las opciones disponibles y vuelve a intentarlo.\n\n"
                "Si tienes alguna duda o necesitas ayuda, no dudes en contactar con el soporte técnico para recibir asistencia inmediata."
            )
        if not is_valid_url(self.rating_link) and self.rta == '1':
            raise ValidationError(
                "El enlace ingresado no es válido. Debe comenzar con 'http://', 'https://', o 'ftp://', "
                "contener un dominio válido como 'example.com' o una dirección IP correctamente escrita como '192.168.1.1'. "
                "No debe incluir espacios ni caracteres no permitidos y, si contiene parámetros o rutas, "
                "deben estar bien formateados. Ej. de URLs válidas: https://www.google.com, "
                "http://miempresa.com/contacto, ftp://servidor-archivos.com. Corrige la URL e inténtalo nuevamente."
            )
        # Agrega el link de la carpeta y la calificación a la oportunidad
        document = self.env['opportunity.type.document'].search(
            [('name', '=', 'Calificación')], limit=1)
        if not document:
            raise UserError(
                "No se ha encontrado el tipo de documento 'Calificación'. "
                "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
        self.lead_id.sudo().write({
            'document_ids': [(0, 0, {
                'type_document_id': document.id,
                'link': self.rating_link if self.rta == '1' else convert_first_letter_to_uppercase(self.reason),
            })],
            'link_document': self.link,
            'stage': 'in_pre_sale',
            # La referencia se genera automáticamente si tiene el valor 'Nuevo'
            # (Se condiciona porque en pipeline.py se crea la secuencia dependiendo de lo que seleccione el usuario)
            'reference': self.lead_id.reference if self.lead_id.reference != 'Nuevo' else self.env['ir.sequence'].next_by_code(
                'opportunity.edm' if self.lead_id.type_opportunity_id.name in ['Estudio de mercado', 'RFI'] else
                'opportunity'
            ),
        })
        template = self.env.ref(
            'opportunities.email_template_new_crm_opportunity')
        if template:
            employee = self.env['opportunity.team'].search(
                [('name', '=', 'Preventa')], limit=1)
            template.sudo().with_context(employee_name=employee.leader_id.employee_id.name).send_mail(self.lead_id.id, email_values={
                'email_to': employee.leader_id.employee_id.work_email,
            })
        # Tiempos (opportunity.timesheet)
        if len(self.lead_id.timesheet_ids) > 0:
            member = self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.uid)], limit=1)
            if not member:
                raise UserError(
                    "No se ha encontrado el miembro del equipo de oportunidades. "
                    "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
        if self.rta == '1':
            msg = Markup(
                f"<span> La documentación para este registro <span style='color: #017e84;'>ha sido cargada exitosamente</span>. "
                f"Puedes verla dando clic <a style='color: #017e84;' href='{self.link}' target='_blank'>aquí</a>.</span>"
            )
        else:
            msg = Markup(
                f"<span> La documentación para este registro <span style='color: #017e84;'>ha sido cargada exitosamente</span>. "
                f"Sin embargo, <span style='color: #017e84;'>no se ha adjuntado</span> el enlace de calificación debido al siguiente motivo: "
                f"<span style='color: #017e84;'>{convert_first_letter_to_uppercase(self.reason)}</span>. </span>"
            )
        wait = self.env['opportunity.timesheet'].search(
            [('lead_id', '=', self.lead_id.id), ('state', '=', 'Esperando cargue de documentación')], limit=1)
        if wait:
            wait.sudo().write({
                'description': msg,
                'state': 'Documentación cargada',
                'end_date': fields.Datetime.now(),
            })
            self.env['opportunity.timesheet'].sudo().create({
                'lead_id': self.lead_id.id,
                'member_id': member.id,
                'description': Markup(
                    f"<span style='color: #017e84;'>Esperando asignación de el equipo de preventa...</span>"
                ),
                'state': 'Esperando asignación equipo de preventa',
                'start_date': fields.Datetime.now(),
            })
        self.lead_id.sudo().message_post(body=msg)
