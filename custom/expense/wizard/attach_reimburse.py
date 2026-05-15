from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
import base64
from markupsafe import Markup
import io
from PyPDF2 import PdfReader, PdfWriter
from ..utils.utils import (
    convert_first_letter_to_uppercase,
    get_accounting_team_emails,
    send_expense_mail,
)


class ExpenseAttachReimburseEvidenceWizard(models.TransientModel):
    _name = 'expense.attach.reimburse.evidence.wizard'
    _description = 'Adjuntar evidencia de reembolso'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    expense_id = fields.Many2one(
        'expense.expense', string='Viático', required=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', related='expense_id.employee_id', readonly=True)
    """BINARY"""
    evidence_file = fields.Binary(string='Evidencia')
    """FLOAT"""
    evidence_amount = fields.Float(
        string='Monto de la evidencia', digits=(16, 0))
    outstanding_amount = fields.Float(
        string='Monto pendiente', compute='_compute_outstanding_amount', digits=(16, 0))
    """BOOLEAN"""
    next_page = fields.Boolean(
        string='Siguiente página', default=False, readonly=True)

    @api.depends('expense_id.requested_amount', 'expense_id.legalized_amount')
    def _compute_outstanding_amount(self):
        for record in self:
            if record.expense_id.approved_amount:
                record.outstanding_amount = record.expense_id.approved_amount - \
                    record.expense_id.legalized_amount
            else:
                record.outstanding_amount = record.expense_id.requested_amount - \
                    record.expense_id.legalized_amount

    def action_next_page(self):
        self.ensure_one()
        self.next_page = True
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.attach.reimburse.evidence.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_back_to_instructions(self):
        self.next_page = False
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.attach.reimburse.evidence.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_no_reimbursement(self):
        template_xmlid = 'expense.mail_template_expense_no_reimbursement'
        self.ensure_one()
        self.expense_id.sudo().message_post(
            body=Markup(
                f"<span>Se confirma que <span style='color: #017e84;'>no se realizará el reembolso</span> "
                f"del valor pendiente de <span style='color: #017e84;'>${self.outstanding_amount:,.0f}</span>.</span>"
            ).replace(',', '.')
        )
        self.expense_id.sudo().write({
            'state': 'legalized',
            'rejected': False,
        })
        contact_emails = [
            self.expense_id.create_uid.email,
            *get_accounting_team_emails(self),
        ]
        send_expense_mail(self.expense_id, template_xmlid, contact_emails)

    def action_attach_evidence(self):
        template_xmlid = 'expense.mail_template_expense_reimbursement_evidence'
        self.ensure_one()
        if not self.evidence_file:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe adjuntar un archivo de evidencia. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                }
            }
        if self.evidence_amount <= 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El monto de la evidencia debe ser mayor a cero. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                }
            }
        if self.evidence_amount > self.outstanding_amount:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El valor de la evidencia no puede ser mayor al saldo pendiente. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                }
            }
        # Valida que el archivo de evidencia sea un PDF
        try:
            file_data = base64.b64decode(self.evidence_file)
            if not file_data.startswith(b'%PDF'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('El archivo adjunto debe ser un PDF. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                    }
                }
        except Exception:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Error al procesar el archivo. Asegúrese de que sea un PDF válido.'),
                    'type': 'danger',
                }
            }

        # Crear adjunto para la evidencia del reembolso
        try:
            # Decodificar el archivo PDF
            file_data = base64.b64decode(self.evidence_file)
            pdf_stream = io.BytesIO(file_data)

            # Leer y comprimir el PDF
            reader = PdfReader(pdf_stream)
            writer = PdfWriter()

            for page in reader.pages:
                # Comprimir imágenes en la página
                page.compress_content_streams()
                writer.add_page(page)

            # Guardar el PDF comprimido
            compressed_stream = io.BytesIO()
            writer.write(compressed_stream)
            compressed_data = compressed_stream.getvalue()
            compressed_base64 = base64.b64encode(compressed_data)

        except ImportError:
            # Si PyPDF2 no está disponible, usar el archivo original
            compressed_base64 = self.evidence_file
        except Exception:
            # Si hay error en la compresión, usar el archivo original
            compressed_base64 = self.evidence_file

        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'Evidencia_Reembolso_{self.expense_id.reference}_{fields.Datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            'datas': compressed_base64,
            'res_model': 'expense.expense',
            'res_id': self.expense_id.id,
            'description': 'Evidencia del reembolso',
            'mimetype': 'application/pdf',
        })

        # Actualizar el monto legalizado
        self.expense_id.sudo().write({
            'legalized_amount': self.expense_id.legalized_amount + self.evidence_amount,
            'attached_reimbursement': True
        })

        self.expense_id.sudo().message_post(
            body=Markup(
                f"<span>Se adjunta <span style='color: #017e84;'>evidencia del reembolso</span> por un valor de "
                f"<span style='color: #017e84;'>${self.evidence_amount:,.0f}</span>.</span>"
            ).replace(',', '.')
        )
        # Determinar el monto objetivo: approved_amount tiene prioridad sobre requested_amount
        target_amount = self.expense_id.approved_amount if (
            self.expense_id.approved_amount and self.expense_id.approved_amount > 0
        ) else self.expense_id.requested_amount
        # Verificar si ya se legalizó todo el monto
        if self.expense_id.legalized_amount == target_amount:
            self.expense_id.sudo().write({
                'state': 'legalized',
                'rejected': False
            })
            self.expense_id.sudo().message_post(
                body=Markup(
                    f"<span>La solicitud ha sido <span style='color: #017e84;'>legalizada completamente</span>, "
                    f"por un valor de: <span style='color: #017e84;'>${self.expense_id.legalized_amount:,.0f}</span>.</span>"
                ).replace(',', '.')
            )
        else:
            if self.expense_id.attached_evidence:
                self.expense_id.sudo().write({
                    'state': 'legalized',
                    'rejected': False
                })
                self.expense_id.sudo().message_post(
                    body=Markup(
                        f"<span>La solicitud ha sido <span style='color: #017e84;'>legalizada</span> por un valor de: "
                        f"<span style='color: #017e84;'>${self.expense_id.legalized_amount:,.0f}</span>. "
                        f"Quedó un saldo pendiente de: <span style='color: #017e84;'>${target_amount - self.expense_id.legalized_amount:,.0f}</span>.</span>"
                    ).replace(',', '.')
                )
        contact_emails = [
            self.expense_id.create_uid.email,
            *get_accounting_team_emails(self),
        ]
        send_expense_mail(
            self.expense_id,
            template_xmlid,
            contact_emails,
            evidence_amount=self.evidence_amount,
        )
