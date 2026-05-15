
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils.utils import is_valid_url, convert_first_letter_to_uppercase
from markupsafe import Markup


class PreSaleRequired(models.TransientModel):
    _name = 'opportunity.pre.sale.required'
    _description = 'Preventa requerida'
    _rec_name = 'lead_id'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    """SELECTION"""
    rta = fields.Selection(
        [('1', 'Si'), ('2', 'No')], string='Respuesta')
    """TEXT"""
    reason = fields.Text(string='Motivo', )
    """CHAR"""
    link = fields.Char(string='Enlace',)
    """BOOLEAN"""
    next_step = fields.Boolean(
        string='¿Siguiente paso?', default=False, readonly=True)

    def action_next(self):
        if not self.lead_id:
            raise ValidationError(
                _("La oportunidad no se ha encontrado, cierra la ventana y vuelve a intentarlo. "
                  "Si el problema persiste, contacta con el administrador del sistema."))
        elif not self.rta:
            raise ValidationError(
                _("Debes seleccionar una respuesta para continuar con la operación. "
                  "Por favor, selecciona una de las opciones disponibles y vuelve a intentarlo."))
        elif not self.reason:
            raise ValidationError(
                _("Debes ingresar un motivo para continuar con la operación. "
                  "Por favor, completa el campo correspondiente y vuelve a intentarlo."))
        if not self.next_step and self.rta == '1':
            self.next_step = True
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'opportunity.pre.sale.required',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
                'context': {'default_lead_id': self.lead_id.id}
            }
        else:
            self.next_step = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'opportunity.pre.sale.required',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
                'context': {'default_lead_id': self.lead_id.id}
            }

    def action_save(self):
        if not self.lead_id:
            raise ValidationError(
                _("La oportunidad no se ha encontrado, cierra la ventana y vuelve a intentarlo. "
                  "Si el problema persiste, contacta con el administrador del sistema."))
        elif not self.rta:
            raise ValidationError(
                _("Debes seleccionar una respuesta para continuar con la operación. "
                  "Por favor, selecciona una de las opciones disponibles y vuelve a intentarlo."))
        elif not self.reason:
            raise ValidationError(
                _("Debes ingresar un motivo para continuar con la operación. "
                  "Por favor, completa el campo correspondiente y vuelve a intentarlo."))
        elif self.rta == '1' and not self.link:
            raise ValidationError(
                _("Debes ingresar un enlace para continuar con la operación. "
                  "Por favor, completa el campo correspondiente y vuelve a intentarlo."))
        elif not is_valid_url(self.link) and self.rta == '1':
            raise ValidationError(
                "El enlace ingresado no es válido. Debe comenzar con 'http://', 'https://', o 'ftp://', "
                "contener un dominio válido como 'example.com' o una dirección IP correctamente escrita como '192.168.1.1'. "
                "No debe incluir espacios ni caracteres no permitidos y, si contiene parámetros o rutas, "
                "deben estar bien formateados. Ej. de URLs válidas: https://www.google.com, "
                "http://miempresa.com/contacto, ftp://servidor-archivos.com. Corrige la URL e inténtalo nuevamente."
            )
        # Determinar estado y mensaje
        requires_support = self.rta == '1'
        status_text = 'Se requiere apoyo del equipo de preventa' if requires_support else 'No es necesario el apoyo del equipo de preventa'
        # Mensaje principal
        msg = Markup(
            f"<span>Se ha {'solicitado' if requires_support else 'indicado que no es necesario'} el "
            f"<span style='color: #017e84;'>apoyo del equipo de preventa</span> "
            f"para {'continuar con el proceso' if requires_support else 'presentar el pipeline'}. "
            f"El motivo registrado es <span style='color: #017e84;'>"
            f"{convert_first_letter_to_uppercase(self.reason)}</span>.</span>"
        )
        # Actualizar estado del lead
        stage_values = {
            'stage': 'in_pre_sale' if requires_support else 'presented'
        }
        if requires_support:
            stage_values['link_document'] = self.link
        self.lead_id.sudo().write(stage_values)
        # Verificar miembro de equipo
        if len(self.lead_id.timesheet_ids) > 0:
            member = self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.uid)], limit=1)
            if not member:
                raise UserError(
                    "No se ha encontrado el miembro del equipo de oportunidades. "
                    "Por favor, contacta con el soporte técnico para recibir asistencia inmediata."
                )
        # Actualizar registro anterior si existe
        wait = self.env['opportunity.timesheet'].search(
            [('lead_id', '=', self.lead_id.id), ('state', '=', 'Esperando respuesta')], limit=1)
        if wait:
            wait.sudo().write({
                'description': msg,
                'state': status_text,
                'end_date': fields.Datetime.now(),
            })
            timesheet_data = []
            if requires_support:
                # Mensaje de documentación
                document = Markup(
                    f"<span>La documentación para este registro <span style='color: #017e84;'>ha sido cargada exitosamente</span>. "
                    f"Puedes verla dando clic <a style='color: #017e84;' href='{self.link}' target='_blank'>aquí</a>.</span>"
                )
                timesheet_data.extend([
                    {
                        'description': document,
                        'state': 'Documentación cargada',
                        'start_date': fields.Datetime.now(),
                        'end_date': fields.Datetime.now(),
                    },
                    {
                        'description': Markup("<span style='color: #017e84;'>Esperando asignación de el equipo de preventa...</span>"),
                        'state': 'Esperando asignación equipo de preventa',
                        'start_date': fields.Datetime.now(),
                    }
                ])
            else:
                presented_msg = Markup(
                    f"<span>Se ha marcado como <span style='color: #017e84;'>presentado</span>.</span>"
                )
                timesheet_data.append({
                    'description': presented_msg,
                    'state': 'Pipeline presentado',
                    'start_date': fields.Datetime.now(),
                    'end_date': fields.Datetime.now(),
                })
            # Crear registros de timesheet
            for entry in timesheet_data:
                entry.update({
                    'lead_id': self.lead_id.id,
                    'member_id': member.id,
                })
                self.env['opportunity.timesheet'].sudo().create(entry)
        self.lead_id.sudo().message_post(body=msg)
