
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..utils.utils import convert_first_letter_to_uppercase, format_html_to_sentence_case, is_html_content_empty, is_valid_url


class ExpenseRefund(models.Model):
    _name = 'expense.refund'
    _description = 'Reintegro'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'reference'

    """MANY2ONE"""
    employee_id = fields.Many2one(
        'hr.employee', string='Responsable', copy=False, required=True,)
    project_id = fields.Many2one(
        'project.management', string='Proyecto', required=True, copy=False, domain="[('prefix', '!=', False)]",)
    enterprise_id = fields.Many2one(
        'expense.enterprise', string='Empresa', copy=False, required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', copy=False, default=lambda self: self.env.company.currency_id)
    """SELECTION"""
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('rejected', 'Rechazado'),
        ('to_approve', 'Por Aprobar'),
        ('to_review', 'Por Revisar'),
        ('legalized', 'Legalizado'),
        ('paid', 'Pagado'),
        ('caused', 'Causado'),
        ('finalized', 'Finalizado'),
    ], string='Estado', default='draft', copy=False, readonly=True,)
    """MONETARY"""
    amount = fields.Monetary(string='Total', copy=False,
                             currency_field='currency_id')
    """DATE"""
    create_date = fields.Date(
        string='Fecha de creación', copy=False, default=fields.Date.context_today, )
    """CHAR"""
    reference = fields.Char(string='Referencia', required=True, copy=False, readonly=True, index=True,
                            default=lambda self: _('Nuevo'))
    subject = fields.Char(string='Asunto', required=True, copy=False)
    """TEXT"""
    reason = fields.Text(string='Motivo', copy=False, required=True)
    """BOOLEAN"""
    has_attached_evidence = fields.Boolean(
        string='¿Tiene evidencia adjunta?', copy=False, readonly=True)

    @api.constrains('amount')
    def _check_amount_positive(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError(
                    _('El total del reintegro debe ser mayor a cero. Por favor, verifique e intente nuevamente.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['subject'] = convert_first_letter_to_uppercase(
                vals.get('subject', ''))
            vals['reason'] = convert_first_letter_to_uppercase(
                vals.get('reason', ''))
        return super(ExpenseRefund, self).create(vals_list)

    def action_view_attached_evidence(self):
        """Abre el visor de evidencia adjunta del reintegro"""
        attachments = self.env['ir.attachment'].sudo().search([
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
        ], order='create_date desc')
        if not attachments:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin evidencia'),
                    'message': _('No hay evidencia adjunta para este reintegro.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        wizard = self.env['expense.refund.view.attachment'].sudo().create({
            'refund_id': self.id,
            'attached_document': attachments[0].datas,
        })
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'expense.refund.view.attachment',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard.id,
        }

    def attach_document(self, **kwargs):
        """Requerido por el widget attach_document.
        El widget ya subió y vinculó el adjunto al registro via /web/binary/upload_attachment.
        Valida que el archivo sea PDF; si no lo es, lo elimina y notifica al usuario.
        """
        attachment_ids = kwargs.get('attachment_ids', [])
        if not attachment_ids:
            return True
        attachment = self.env['ir.attachment'].browse(attachment_ids[-1])
        if not attachment.exists():
            return True
        if attachment.mimetype != 'application/pdf':
            attachment.sudo().unlink()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('El archivo que intenta adjuntar no es un PDF. Por favor, verifique e intente nuevamente.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        attachment.write({
            'res_model': self._name,
            'res_id': self.id,
        })
        self.has_attached_evidence = True
        return True

    def action_send_for_approval(self):
        """Envía el reintegro a aprobación"""
        for record in self:
            if record.state not in ['draft', 'rejected']:
                raise UserError(
                    _('Solo se pueden enviar para aprobación los reintegros en estado Borrador o Rechazado. Por favor, verifique e intente nuevamente.'))
            elif not record.has_attached_evidence:
                raise UserError(
                    _('Debe adjuntar la evidencia correspondiente antes de enviar el reintegro para aprobación. Por favor, adjunte el documento y vuelva a intentarlo.'))
            record.state = 'to_approve'
            record.reference = 'RET/' + self.enterprise_id.prefix + \
                self.env['ir.sequence'].next_by_code(
                    'expense.refund') or 'Nuevo'

    def action_approve(self):
        """Aprueba el reintegro"""
        for record in self:
            if record.state not in ['to_approve', 'to_review']:
                raise UserError(
                    _('Solo se pueden aprobar los reintegros en estado Por Aprobar o Por Revisar. Por favor, verifique e intente nuevamente.'))
            record.state = 'to_review' if record.state == 'to_approve' else 'legalized'

    def action_reject(self):
        """Rechaza el reintegro"""
        for record in self:
            if record.state not in ['to_approve', 'to_review']:
                raise UserError(
                    _('Solo se pueden rechazar los reintegros en estado Por Aprobar o Por Revisar. Por favor, verifique e intente nuevamente.'))
            record.state = 'rejected'
            attachments = self.env['ir.attachment'].sudo().search([
                ('res_id', '=', record.id),
                ('res_model', '=', record._name),
            ])
            attachments.sudo().unlink()
            record.has_attached_evidence = False
    
    def action_pay(self):
        """Marca el reintegro como Pagado"""
        for record in self:
            if record.state != 'legalized':
                raise UserError(
                    _('Solo se pueden marcar como pagados los reintegros en estado Legalizado. Por favor, verifique e intente nuevamente.'))
            record.state = 'paid'

    def action_cause(self):
        """Causa el reintegro"""
        for record in self:
            if record.state != 'paid':
                raise UserError(
                    _('Solo se pueden causar los reintegros en estado Pagado. Por favor, verifique e intente nuevamente.'))
            record.state = 'caused'

    def action_finalize(self):
        """Finaliza el reintegro"""
        for record in self:
            if record.state != 'caused':
                raise UserError(
                    _('Solo se pueden finalizar los reintegros en estado Causado. Por favor, verifique e intente nuevamente.'))
            record.state = 'finalized'
