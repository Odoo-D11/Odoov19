
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..utils.utils import is_valid_url
from markupsafe import Markup


class CrmUploadOffer(models.TransientModel):
    _name = 'upload.offer'
    _description = 'Subir oferta'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', required=True, readonly=True)
    """FLOAT"""
    value = fields.Float(string='Valor', digits=(16, 0))
    """CHAR"""
    link = fields.Char(string='Enlace', required=True)
    """BOOLEAN"""
    edm = fields.Boolean(string='EDM', default=False, readonly=True)
    next_step = fields.Boolean(
        string='Siguiente paso', default=False, readonly=True)

    def action_upload_offer(self):
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
        offer = self.env['opportunity.type.document'].search(
            [('name', '=', 'Oferta')], limit=1)
        if not offer:
            raise ValidationError(_(
                "No se ha encontrado el tipo de documento 'Oferta'. "
                "Esto puede deberse a que no se ha configurado correctamente en el sistema. "
                "Por favor, contacte con el administrador del sistema para revisar la configuración."
            ))
        if not is_valid_url(self.link):
            raise ValidationError(
                "El enlace ingresado no es válido. Debe comenzar con 'http://', 'https://', o 'ftp://', "
                "contener un dominio válido como 'example.com' o una dirección IP correctamente escrita como '192.168.1.1'. "
                "No debe incluir espacios ni caracteres no permitidos y, si contiene parámetros o rutas, "
                "deben estar bien formateados. Ej. de URLs válidas: https://www.google.com, "
                "http://miempresa.com/contacto, ftp://servidor-archivos.com. Corrige la URL e inténtalo nuevamente."
            )
        if self.edm and self.value <= 0:
            raise ValidationError(
                "Debes ingresar un valor para la oferta si se trata de un Estudio de mercado. "
                "Por favor, ingresa el valor de la oferta e inténtalo nuevamente."
            )
        document = self.lead_id.document_ids.filtered(
            lambda d: d.type_document_id.id == offer.id)
        if document:
            if self.edm:
                document.sudo().write({'link': self.link})
                self.lead_id.sudo().write({'budget': self.value})
                msg = Markup(
                    f"Se actualizo la oferta para este registro. "
                    f"Puedes verla dando clic <a style='color: #017e84;' href='{self.link}' target='_blank'>aquí</a>."
                )
        else:
            vals = {
                'document_ids': [(0, 0, {'type_document_id': offer.id, 'link': self.link})],
                'budget': self.value if self.edm else self.lead_id.budget,
                'stage': 'pte_present',
                'stage_pre_sale': 'delivered',
            }
            # Tiempos (opportunity.timesheet)
            if len(self.lead_id.timesheet_ids) > 0:
                member = self.env['opportunity.team.member'].search(
                    [('employee_id.user_id', '=', self.env.uid)], limit=1)
                if not member:
                    raise ValidationError(
                        "No se encontro el miembro del equipo de oportunidades. "
                        "Por favor, contacta con el soporte técnico para recibir asistencia inmediata.")
            wait_offer = self.env['opportunity.timesheet'].search(
                [('lead_id', '=', self.lead_id.id), ('state', '=', 'Esperando cargue de oferta')], limit=1)
            self.lead_id.sudo().write(vals)
            msg = Markup(
                f"<span>Se cargo una oferta para este registro. "
                f"Puedes verla dando clic <a style='color: #017e84;' href='{self.link}' target='_blank'>aquí</a>.</span>"
            )
            if wait_offer:
                wait_offer.sudo().write({
                    'description': msg,
                    'state': 'Oferta cargada',
                    'end_date': fields.Datetime.now(),
                })
                self.env['opportunity.timesheet'].sudo().create({
                    'lead_id': self.lead_id.id,
                    'member_id': member.id,
                    'description': Markup(
                        f"<span style='color: #017e84;'>Esperando a presentar la oferta...</span>"
                    ),
                    'state': 'Esperando a presentar la oferta',
                    'start_date': fields.Datetime.now(),
                })
        self.lead_id.sudo().message_post(body=msg)

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
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.offer',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
        else:
            self.next_step = False
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'upload.offer',
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
            }
