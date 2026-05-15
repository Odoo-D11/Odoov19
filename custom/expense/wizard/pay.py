
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup
from ..utils.utils import get_treasury_team_emails, send_expense_mail, is_valid_url


class ExpensePayDisplacement(models.TransientModel):
    _name = 'expense.pay.displacement'
    _description = 'Desplazamientos para el pago de la solicitud'
    _transient_max_count = 50
    _transient_max_hours = 24

    """MANY2ONE"""
    wizard_id = fields.Many2one(
        'expense.pay.wizard', string='Wizard', )
    ticket_id = fields.Many2one(
        'expense.type.ticket', string='Tiquete', )
    origin_id = fields.Many2one('res.city', string='Origen', required=True)
    destination_id = fields.Many2one(
        'res.city', string='Destino', required=True)
    """HTML"""
    resume = fields.Html(string='Resumen', readonly=True)
    """DATETIME"""
    initial_date = fields.Datetime(string='Fecha de inicio', required=True)
    final_date = fields.Datetime(string='Fecha de finalización')
    suggested_initial_date = fields.Datetime(string='Inicio', )
    suggested_final_date = fields.Datetime(string='Fin', )
    """SELECTION"""
    modality_type = fields.Selection([
        ('one_way', 'Solo ida'),
        ('round_trip', 'Ida y vuelta'),
    ], string='Modalidad', )

    @api.constrains('initial_date', 'final_date', 'suggested_initial_date', 'suggested_final_date')
    def _check_dates(self):
        # Las fechas sugeridas no pueden ser menores a las fechas de inicio o fin
        for record in self:
            if record.suggested_initial_date and record.suggested_initial_date < record.initial_date:
                raise ValidationError(
                    _('La fecha sugerida de inicio (%s) no puede ser menor que la fecha de inicio (%s). Por favor, verifique e intente de nuevo.') % (
                        record.suggested_initial_date, record.initial_date)
                )
            if record.suggested_final_date and record.suggested_final_date < record.final_date:
                raise ValidationError(
                    _('La fecha sugerida de finalización (%s) no puede ser menor que la fecha de finalización (%s). Por favor, verifique e intente de nuevo.') % (
                        record.suggested_final_date, record.final_date)
                )


class ExpensePayWizard(models.TransientModel):
    _name = 'expense.pay.wizard'
    _description = 'Pagar solicitud'
    _transient_max_count = 50
    _transient_max_hours = 24

    """ONE2MANY"""
    displacement_ids = fields.One2many(
        'expense.pay.displacement', 'wizard_id', string='Ajustes',)
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', readonly=True)
    """MANY2ONE"""
    expense_id = fields.Many2one(
        'expense.expense', string='Solicitud', required=True, readonly=True, ondelete='cascade')
    category_id = fields.Many2one(
        'expense.category', string='Categoría', required=True, related='expense_id.category_id', readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Empleado', domain="[('id', '=', sequence)]")
    partner_id = fields.Many2one(
        'res.partner', string='Contacto', domain="[('id', '=', sequence)]")
    bank_id = fields.Many2one(
        'res.bank', string='Banco')
    identification_type_id = fields.Many2one(
        'identification.type', string='Tipo de Identificación', required=True)
    country_id = fields.Many2one('res.country', string='País', domain="[('code', '=', 'CO')]",
                                 default=lambda self: self.env.ref('base.co'), readonly=True)
    type_account_id = fields.Many2one(
        'hr.type.account', string='Cuenta', )
    """CHAR"""
    identification_number = fields.Char(
        string='Nro. de Identificación', required=True)
    job_title = fields.Char(string='Título del Trabajo', )
    bank_account = fields.Char(string='Cuenta Bancaria', )
    private_email = fields.Char(
        string='Correo electrónico', required=True)
    private_phone = fields.Char(
        string='Teléfono', required=True)
    link = fields.Char(string='Enlace', )
    airline = fields.Char(string='Aerolínea', )
    reservation_code = fields.Char(string='Cód. de reserva', )
    """DATE"""
    birthday = fields.Date(string='Fecha de Nacimiento', )

    @api.model
    def default_get(self, fields):
        res = super(ExpensePayWizard, self).default_get(fields)
        if 'expense_id' in fields and self._context.get('active_model') == 'expense.expense':
            expense_id = self._context.get('active_id')
            if expense_id:
                expense = self.env['expense.expense'].browse(expense_id)
                res['expense_id'] = expense_id
                if expense.employee_id:
                    res['employee_id'] = expense.employee_id.id
                    res['sequence'] = expense.employee_id.id
                    res['job_title'] = expense.employee_id.job_title
                    if expense.employee_id.bank_id:
                        res['bank_id'] = expense.employee_id.bank_id.id
                        res['bank_account'] = expense.employee_id.bank_account_number
                        res['type_account_id'] = expense.employee_id.type_account_id.id
                    if expense.employee_id.identification_type_id:
                        res['identification_type_id'] = expense.employee_id.identification_type_id.id
                        res['identification_number'] = expense.employee_id.identification_id
                    if expense.employee_id.private_email:
                        res['private_email'] = expense.employee_id.private_email
                    if expense.employee_id.private_phone:
                        res['private_phone'] = expense.employee_id.private_phone
                if expense.partner_id:
                    """Valida si el contacto está relacionado con un empleado"""
                    employee = self.env['expense.personal.information'].search(
                        [('partner_id', '=', expense.partner_id.id)], limit=1)
                    res['partner_id'] = expense.partner_id.id
                    if employee:
                        res['sequence'] = expense.partner_id.id
                        res['private_email'] = employee.email
                        res['private_phone'] = employee.phone
                        res['job_title'] = employee.job_title
                        res['identification_type_id'] = employee.identification_type_id.id
                        res['identification_number'] = employee.nuid
                        res['birthday'] = employee.birth_date
                    # Crear desplazamientos basados en la solicitud
                    displacement_vals = [
                        (0, 0, {
                            'ticket_id': ticket.ticket_id.id,
                            'origin_id': ticket.origin_id.id,
                            'destination_id': ticket.destination_id.id,
                            'initial_date': ticket.initial_date,
                            'final_date': ticket.final_date,
                            'modality_type': ticket.modality_type,
                        }) for ticket in expense.sudo().displacement_ids
                    ]
                    res['displacement_ids'] = displacement_vals

        return res

    def action_pay(self):
        self.ensure_one()
        template_xmlid = 'expense.mail_template_expense_pay'
        contact_emails = [
            self.expense_id.create_uid.email,
            *get_treasury_team_emails(self),
        ]
        if self.category_id.name != 'Viáticos (Alimentación, Hospedaje, etc.)':
            if not self.link:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Requiere ingresar un enlace para el tiquete. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            elif not is_valid_url(self.link):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('El enlace ingresado no es válido. Debe comenzar con "http://", "https://", o "ftp://", '
                                     'contener un dominio válido como "example.com" o una dirección IP correctamente escrita como "192.168.1.1".'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            elif not self.airline:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Requiere ingresar la aerolínea para el tiquete. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            elif not self.reservation_code:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': _('Requiere ingresar el código de reserva para el tiquete. Por favor, verifique e intente nuevamente.'),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            send_expense_mail(
                self.expense_id,
                template_xmlid,
                [self.partner_id.email],
                cc=contact_emails,
                displacement=self.displacement_ids,
                airline=self.airline,
                reservation_code=self.reservation_code,
                link=self.link,
                email=self.private_email,
            )
            self.expense_id.sudo().write({
                'state': 'paid',
                'active': False,
            })
            self.expense_id.sudo().message_post(
                body=Markup(
                    f"<span>El tiquete fue <span style='color: #017e84;'>pagado</span>.</span>"
                )
            )
        else:
            send_expense_mail(
                self.expense_id,
                template_xmlid,
                [self.employee_id.work_email],
                cc=contact_emails,
            )
            self.expense_id.sudo().write({
                'state': 'to_legalize'
            })
            """Le asigna el valor aprobado a la bolsa del empleado"""
            member = self.env['hr.employee'].search(
                [('id', '=', self.employee_id.id)], limit=1)
            if member:
                member.sudo().write({
                    'bag': member.bag + self.expense_id.approved_amount if self.expense_id.approved_amount else member.bag + self.expense_id.requested_amount
                })
            else:
                raise UserError(
                    _('El empleado no se encontró. Por favor, comuníquese con soporte.'))
            self.expense_id.sudo().message_post(
                body=Markup(
                    f"<span>La solicitud ha sido <span style='color: #017e84;'>procesada y pagada</span> exitosamente, "
                    f"por un valor de: <span style='color: #017e84;'>${self.expense_id.approved_amount if self.expense_id.approved_amount else self.expense_id.requested_amount:,.0f}</span>.</span>"
                ).replace(',', '.')
            )
