from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup
from ..utils.utils import convert_first_letter_to_uppercase, send_expense_mail


class ExpenseApproveLegalizationWizard(models.TransientModel):
    _name = 'expense.approve.legalization.wizard'
    _description = 'Aprobar legalización'
    _rec_name = 'expense_id'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    expense_id = fields.Many2one(
        'expense.expense', string='Solicitud', required=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', related='expense_id.employee_id', readonly=True)
    """FLOAT"""
    legalization_amount = fields.Float(
        string='Monto de la legalización', digits=(16, 0), related='expense_id.legalized_amount', readonly=True)
    """SELECTION"""
    rta = fields.Selection([
        ('yes', 'Sí'),
        ('no', 'No')
    ], string='Respuesta', )
    reason = fields.Selection(
        [('evidence', 'Evidencia'),
         ('reimbursement', 'Reembolso'), ('both', 'Ambos')],
        string='Motivo',)
    view_mode = fields.Selection([
        ('instructions', 'Instrucciones'),
        ('evidence', 'Ver Evidencia'),
        ('reimbursement', 'Ver Reembolso'),
        ('response', 'Responder')
    ], string='Modo de Vista', default='instructions')
    previous_view = fields.Selection([
        ('instructions', 'Instrucciones'),
        ('evidence', 'Ver Evidencia'),
        ('reimbursement', 'Ver Reembolso'),
        ('response', 'Responder')
    ], string='Vista Anterior', default='instructions')
    """TEXT"""
    rejection_justification = fields.Text(
        string='Justificación de rechazo', )
    """BINARY"""
    attached_evidence = fields.Binary(
        string='Evidencia Adjunta', readonly=True)
    attached_reimbursement = fields.Binary(
        string='Reembolso Adjunto', readonly=True)
    """BOOLEAN"""
    has_evidence = fields.Boolean(
        string='Tiene Evidencia', compute='_compute_has_files', store=False)
    has_reimbursement = fields.Boolean(
        string='Tiene Reembolso', compute='_compute_has_files', store=False)

    @api.depends('attached_evidence', 'attached_reimbursement')
    def _compute_has_files(self):
        for record in self:
            record.has_evidence = bool(record.attached_evidence)
            record.has_reimbursement = bool(record.attached_reimbursement)

    def action_show_evidence(self):
        """Mostrar vista de evidencia"""
        self.previous_view = self.view_mode
        self.view_mode = 'evidence'
        return self._return_wizard_view()

    def action_show_reimbursement(self):
        """Mostrar vista de reembolso"""
        self.previous_view = self.view_mode
        self.view_mode = 'reimbursement'
        return self._return_wizard_view()

    def action_show_response(self):
        """Mostrar vista de respuesta"""
        if self.rta == 'no':
            self.rta = False  # Resetear para que pueda seleccionar nuevamente
        self.previous_view = self.view_mode
        self.view_mode = 'response'
        return self._return_wizard_view()

    def action_back_to_instructions(self):
        """Volver a instrucciones"""
        self.view_mode = 'instructions'
        self.previous_view = 'instructions'
        return self._return_wizard_view()

    def action_back_to_previous(self):
        """Volver a la vista anterior con lógica mejorada"""
        if self.view_mode == 'response' and self.rta == 'no':
            # Si estamos en rechazo, volver a la vista de respuesta
            self.rta = False
            return self._return_wizard_view()
        elif self.view_mode in ['evidence', 'reimbursement']:
            # Si estamos en evidencia o reembolso, siempre volver a instrucciones
            self.view_mode = 'instructions'
            self.previous_view = 'instructions'
            return self._return_wizard_view()
        else:
            # Para otros casos, volver a la vista anterior guardada
            current_view = self.view_mode
            self.view_mode = self.previous_view or 'instructions'
            self.previous_view = current_view
            return self._return_wizard_view()

    def _return_wizard_view(self):
        """Retornar la vista del wizard actual"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'expense.approve.legalization.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context
        }

    def action_approve_legalization(self):
        template_rejection_xmlid = 'expense.mail_template_expense_no_legalization'
        template_approval_xmlid = 'expense.mail_template_expense_legalization_approved'
        if not self.rta:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Debe seleccionar una respuesta. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        self.ensure_one()
        if self.rta == 'yes':
            self.expense_id.sudo().write({
                'state': 'approved_evidence',
            })
            self.expense_id.sudo().message_post(
                body=Markup(
                    f"<span>La legalización ha sido <span style='color: #017e84;'>aprobada exitosamente</span> "
                    f"por un valor de <span style='color: #017e84;'>${self.expense_id.legalized_amount:,.0f}</span>.</span>"
                ).replace(',', '.')
            )
            """Se resta de la bolsa del empleado el valor legalizado"""
            member = self.env['hr.employee'].search(
                [('id', '=', self.expense_id.employee_id.id)], limit=1)
            if member:
                member.sudo().write({
                    'bag': member.bag - self.expense_id.legalized_amount
                })
            else:
                raise UserError(
                    _('El empleado no se encontró. Por favor, comuníquese con soporte.'))
            send_expense_mail(
                self.expense_id,
                template_approval_xmlid,
                [self.expense_id.employee_id.work_email],
                cc=[self.expense_id.create_uid.email],
            )
        elif self.rta == 'no':
            if not self.rejection_justification:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Debe indicar una justificación de rechazo. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            reason_text = convert_first_letter_to_uppercase(
                self.rejection_justification.replace('\n', ' ')
            )
            if self.reason == 'evidence':
                self.expense_id.message_post(
                    body=Markup(
                        f"<span>Se <span style='color: #017e84;'>rechazó la evidencia</span> de la solicitud "
                        f"por la siguiente razón: "
                        f"<span style='color: #017e84;'>{reason_text}</span>. "
                    )
                )
            elif self.reason == 'reimbursement':
                self.expense_id.message_post(
                    body=Markup(
                        f"<span>Se <span style='color: #017e84;'>rechazado el reembolso</span> de la solicitud "
                        f"por la siguiente razón: "
                        f"<span style='color: #017e84;'>{reason_text}</span>. "
                    )
                )
            elif self.reason == 'both':
                self.expense_id.message_post(
                    body=Markup(
                        f"<span>Se <span style='color: #017e84;'>rechazó la evidencia y el reembolso</span> "
                        f"de la solicitud por la siguiente razón: "
                        f"<span style='color: #017e84;'>{reason_text}</span>. "
                    )
                )
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Debe indicar un motivo de rechazo. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            self.expense_id.sudo().write({
                'state': 'to_legalize',
                'rejected': True,
                'attached_evidence': False,
                'attached_reimbursement': False,
                'legalized_amount': 0
            })
            """Elimina los archivos adjuntos"""
            attachments = self.env['ir.attachment'].search([
                ('res_id', '=', self.expense_id.id),
                ('res_model', '=', 'expense.expense')
            ])
            attachments.sudo().unlink()
            send_expense_mail(
                self.expense_id,
                template_rejection_xmlid,
                [self.expense_id.employee_id.work_email],
                cc=[self.expense_id.create_uid.email],
                reason=dict(self._fields['reason'].selection).get(
                    self.reason, ''),
                justification=convert_first_letter_to_uppercase(
                    self.rejection_justification.replace('\n', ' ')
                ),
            )
