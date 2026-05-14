import base64
import os
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup


class PurchaseOrderSendMailWizard(models.TransientModel):
    _name = 'purchase.order.send.mail.wizard'
    _description = 'Wizard para enviar correo de Orden de Compra'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    order_id = fields.Many2one(
        'purchase.management.order', string='Orden de Compra',
        required=True, readonly=True)
    """CHAR"""
    subject = fields.Char(string='Asunto', required=True)
    technical_sheet_filename = fields.Char(string='Nombre del archivo')
    """BINARY"""
    technical_sheet = fields.Binary(string='Ficha técnica')
    """HTML"""
    body_html = fields.Html(string='Cuerpo del correo', sanitize=False)
    """SELECTION"""
    step = fields.Selection([
        ('attachment', 'Adjunto'),
        ('preview', 'Vista previa'),
    ], string='Paso', default='attachment', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = self.env.context.get('default_order_id') or res.get('order_id')
        if not order_id:
            return res

        order = self.env['purchase.management.order'].browse(order_id)
        if not order.exists():
            return res

        res.setdefault('subject', order.subject)

        template = self.env.ref(
            'purchase_management.mail_template_purchase_order',
            raise_if_not_found=False)
        if template:
            rendered_body = template._render_field(
                'body_html', [order.id], compute_lang=False)
            res.setdefault('body_html', rendered_body.get(order.id, ''))

        return res

    @api.constrains('technical_sheet', 'technical_sheet_filename')
    def _check_technical_sheet(self):
        MAX_SIZE = 10 * 1024 * 1024  # 10 MB
        ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx'}
        for record in self:
            if record.technical_sheet and record.technical_sheet_filename:
                ext = os.path.splitext(record.technical_sheet_filename)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    raise ValidationError(
                        _('Solo se permiten archivos PDF o Word (.pdf, .doc, .docx).'))
                file_size = len(base64.b64decode(record.technical_sheet))
                if file_size > MAX_SIZE:
                    raise ValidationError(
                        _('El archivo no puede superar los 10 MB.'))

    def action_next(self):
        self.ensure_one()
        if not self.technical_sheet:
            raise UserError(_('Debe adjuntar la ficha técnica antes de continuar.'))
        self.step = 'preview'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_back(self):
        self.ensure_one()
        self.step = 'attachment'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_send_mail(self):
        self.ensure_one()
        order = self.order_id

        attachment_ids = []

        # PDF de la OC
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            'purchase_management.action_report_purchase_order', [order.id])
        pdf_attachment = self.env['ir.attachment'].sudo().create({
            'name': '%s.pdf' % order.reference,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'purchase.management.order',
            'res_id': order.id,
            'mimetype': 'application/pdf',
        })
        attachment_ids.append((4, pdf_attachment.id))

        # Ficha técnica (si se adjuntó)
        if self.technical_sheet and self.technical_sheet_filename:
            _mimetype_map = {
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            }
            ext = os.path.splitext(self.technical_sheet_filename)[1].lower()
            sheet_attachment = self.env['ir.attachment'].sudo().create({
                'name': self.technical_sheet_filename,
                'type': 'binary',
                'datas': self.technical_sheet,
                'res_model': 'purchase.management.order',
                'res_id': order.id,
                'mimetype': _mimetype_map.get(ext, 'application/octet-stream'),
            })
            attachment_ids.append((4, sheet_attachment.id))

        mail_values = {
            'subject': self.subject,
            'body_html': self.body_html,
            'email_to': order.partner_id.email or '',
            'email_from': 'odoo@tsg.net.co',
            'attachment_ids': attachment_ids,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.sudo().send()

        order.sudo().write({'state': 'sent'})

        msg = Markup(
            "<span>Orden de compra <span style='color: #017e84;'>%s</span> enviada por correo "
            "a <span style='color: #017e84;'>%s</span>%s.</span>"
        ) % (
            order.reference,
            order.partner_id.email or order.partner_id.name,
            Markup(" con ficha técnica adjunta") if self.technical_sheet else Markup(""),
        )
        order.sudo().message_post(body=msg)

        return {'type': 'ir.actions.act_window_close'}
