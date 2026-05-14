# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from markupsafe import Markup
import re
from ..utils.utils import (  # type: ignore
    is_valid_url
)


"""class InheritHrEmployeeBase(models.AbstractModel):
    _inherit = ['hr.employee.base']

    def _inverse_work_contact_details(self):
        employees_without_work_contact = self.env['hr.employee']
        for employee in self:
            if not employee.work_contact_id:
                employees_without_work_contact += employee
            else:
                employee.work_contact_id.sudo().write({
                    'email': employee.work_email,
                    'phone': employee.mobile_phone,
                })
        if employees_without_work_contact:
            employees_without_work_contact.sudo()._create_work_contacts()

    def _create_work_contacts(self):
        if any(employee.work_contact_id for employee in self):
            raise UserError(
                _('Algunos empleados ya tienen un contacto de trabajo asignado.'))
        with self.env.cr.savepoint():
            self = self.with_context(skip_vat_validation=True)
            company = self.env['res.company'].search(
                [('id', '=', self.env.user.company_id.id)]).partner_id
            work_contacts = self.env['res.partner'].create([{
                'email': employee.work_email,
                'phone': employee.mobile_phone,
                'name': employee.name,
                'image_1920': employee.image_1920,
                'company_id': employee.company_id.id,
                'is_employee': True,
                'identification_type_id': company.identification_type_id.id,
                'vat': company.vat,
                'parent_id': company.id,
                'street': company.street,
                'title': self.env['res.partner.title'].search([('name', '=', 'Sr.')], limit=1).id if employee.gender == 'male' else self.env['res.partner.title'].search([('name', '=', 'Sra.')], limit=1).id,
                'state_id': company.state_id.id,
                'city_id': company.city_id.id,
                'country_id': company.country_id.id,
            } for employee in self])
            for employee, work_contact in zip(self, work_contacts):
                employee.work_contact_id = work_contact"""


class InheritHrEmployee(models.Model):
    _inherit = 'hr.employee'

    """ONE2MANY"""
    additional_income_ids = fields.One2many(
        'hr.employee.additional.income', 'employee_id', string='Ingresos adicionales', )
    experience_ids = fields.One2many(
        'hr.experience', 'employee_id', string='Experiencia laboral', )
    certification_ids = fields.One2many(
        'hr.certification', 'employee_id', string='Certificaciones', )
    """MANY2ONE"""
    enterprise_id = fields.Many2one(
        'hr.enterprise', string='Empresa', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    department_id = fields.Many2one(
        'hr.department', string='Área', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    coach_id = fields.Many2one(
        'hr.employee', string='Jefe inmediato', domain="[('id', '!=', id)]",)
    identification_type_id = fields.Many2one(
        'identification.type', string='Tipo de identificación', domain="[('code', 'not in', ('NIT', 'VAT', 'PAS'))]", groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    city_of_birth_id = fields.Many2one(
        'res.city', string='Ciudad de nacimiento', groups='hr.group_hr_user,rrhh.group_creator_rrhh', )
    state_of_birth_id = fields.Many2one(
        'res.country.state', string='Departamento de nacimiento', groups='hr.group_hr_user,rrhh.group_creator_rrhh', )
    country_id = fields.Many2one('res.country', string='Nacionalidad (País)',
                                 default=lambda self: self.env.ref('base.co'))
    private_city_id = fields.Many2one(
        'res.city', string='Ciudad privada', )
    type_account_id = fields.Many2one(
        'hr.type.account', string='Cuenta', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    bank_id = fields.Many2one(
        'res.bank', string='Banco', domain="[('active', '=', True)]", groups='hr.group_hr_user,rrhh.group_creator_rrhh', )
    project_id = fields.Many2one(
        'project.management', string='Proyecto', )
    cost_center_id = fields.Many2one(
        'cost.center', string='Centro de costo', domain="[('project_id', '=', project_id)]", )
    rh_id = fields.Many2one(
        'rh.rh', string='Grupo RH', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    eps_id = fields.Many2one(
        'hr.eps', groups='hr.group_hr_user,rrhh.group_creator_rrhh', string='EPS',)
    compensation_fund_id = fields.Many2one('hr.compensation.fund', groups='hr.group_hr_user,rrhh.group_creator_rrhh',
                                           string='Caja de compensación',)
    pension_id = fields.Many2one(
        'hr.pension', string='Pensión', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    severance_fund_id = fields.Many2one(
        'hr.severance.fund', string='Cesantías', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    arl_id = fields.Many2one(
        'hr.arl', string='ARL', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    marital_status_id = fields.Many2one(
        'hr.marital.status', string='Estado civil', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    type_of_contract = fields.Many2one(
        'hr.contract.type', string='Tipo de contrato', groups='hr.group_hr_user,rrhh.group_creator_rrhh', domain="[('country_id.code', '=', 'CO')]")
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', groups='hr.group_hr_user,rrhh.group_creator_rrhh', default=lambda self: self.env.ref('base.COP'), readonly=False)
    """DATE"""
    date_of_issue = fields.Date(
        string='Fecha de expedición', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    entry_date = fields.Date(
        string='Fecha de ingreso', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    birthday = fields.Date(
        string='Fecha de nacimiento', groups=None, )
    """SELECTION"""
    gender = fields.Selection([
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro')
    ], string='Género', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    salary_type = fields.Selection([
        ('basic', 'Básico'),
        ('integral', 'Integral')
    ], string='Tipo de salario', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    """FLOAT"""
    wage = fields.Float(
        string='Salario', digits=(16, 0), groups='hr.group_hr_user,rrhh.group_creator_rrhh')
    """CHAR"""
    identification_id = fields.Char(
        string='Nro. identificación', tracking=True, groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    bank_account_number = fields.Char(
        string='Cuenta bancaria', help='Número de cuenta bancaria del empleado', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    private_phone = fields.Char(
        string='Teléfono privado', help='Número de teléfono privado del empleado')
    private_email = fields.Char(
        string='Correo electrónico privado', help='Correo electrónico privado del empleado')
    mobile_phone = fields.Char(
        string='Celular de trabajo', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    age = fields.Char(string='Edad', compute='_compute_age',
                      readonly=False, groups='hr.group_hr_user,rrhh.group_creator_rrhh', )
    folder = fields.Char(
        string='Carpeta', groups='hr.group_hr_user,rrhh.group_creator_rrhh',)
    """BOOLEAN"""
    requires_children = fields.Boolean(string='Requiere hijos', default=False)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        domain = self._certification_search_to_and(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    @api.model
    def _certification_search_to_and(self, domain):
        if not domain:
            return domain
        result = list(domain)
        i = 0
        while i < len(result):
            if result[i] != '|':
                i += 1
                continue
            j = i
            while j < len(result) and result[j] == '|':
                j += 1
            num_ops = j - i
            cert_slice = result[j:j + num_ops + 1]
            if (len(cert_slice) == num_ops + 1 and
                    all(isinstance(c, (list, tuple)) and len(c) == 3 and
                        str(c[0]).startswith('certification_ids') for c in cert_slice)):
                for k in range(i, j):
                    result[k] = '&'
                i = j + num_ops + 1
            else:
                i += 1
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' in vals:
                vals['name'] = vals['name'].title()
        return super(InheritHrEmployee, self).create(vals_list)

    def write(self, vals):
        if self.env.context.get('skip_age_correction'):
            return super(InheritHrEmployee, self).write(vals)
        res = super(InheritHrEmployee, self).write(vals)
        for rec in self.filtered(lambda r: r.birthday):
            expected = f"{fields.Date.today().year - rec.birthday.year - ((fields.Date.today().month, fields.Date.today().day) < (rec.birthday.month, rec.birthday.day))} años"
            if expected and rec.age != expected:
                rec.with_context(skip_age_correction=True).sudo().write(
                    {'age': expected})
        return res

    @api.constrains('folder')
    def _check_folder_url(self):
        for record in self:
            if record.folder and not is_valid_url(record.folder):
                raise ValidationError(
                    _('La URL de la carpeta no es válida. Por favor, ingrese una URL válida o deje el campo vacío.'))

    @api.depends('birthday')
    def _compute_age(self):
        for rec in self:
            today = fields.Date.today()
            if rec.birthday:
                age = today.year - rec.birthday.year - (
                    (today.month, today.day) < (rec.birthday.month, rec.birthday.day))
                rec.age = f"{age} años"
            else:
                rec.age = False

    @api.constrains('private_phone', 'mobile_phone', 'country_id')
    def _check_phone_format(self):
        for record in self:
            for phone_field in ['private_phone', 'mobile_phone']:
                phone_value = getattr(record, phone_field)
                if phone_value:
                    # Validación de patrones irreales
                    clean_phone = re.sub(r'\D', '', phone_value)
                    if len(set(clean_phone)) == 1:
                        raise ValidationError(
                            f"El campo {record.fields_get([phone_field])[phone_field]['string']} no es obligatorio. Sin embargo, si se completa, no puede estar compuesto por un solo dígito repetido. "
                            "Por ejemplo, '1111111' no es válido."
                        )
                    if clean_phone in '0123456789' or clean_phone in '9876543210':
                        raise ValidationError(
                            f"El campo {record.fields_get([phone_field])[phone_field]['string']} no es obligatorio. Sin embargo, si se completa, no puede ser una secuencia numérica simple. "
                            "Por ejemplo, '123456789' o '987654321' no son válidos."
                        )

                    country_code = record.country_id.code.upper() if record.country_id else None

                    if country_code == 'CO':
                        if not re.match(r'^[0-9]{3} [0-9]{7}$', phone_value):
                            formatted_phone = self._format_phone(phone_value)
                            if not formatted_phone:
                                raise ValidationError(
                                    f"El campo {record.fields_get([phone_field])[phone_field]['string']} no es obligatorio. Sin embargo, si se completa, debe cumplir con el formato válido para Colombia. "
                                    "Ejemplo válido: 300 1234567."
                                )
                            setattr(record, phone_field, formatted_phone)
                    else:
                        if not re.match(r'^[0-9]{7,15}$', phone_value):
                            raise ValidationError(
                                f"El campo {record.fields_get([phone_field])[phone_field]['string']} no es obligatorio. Sin embargo, si se completa, debe contener solo números y tener una longitud entre 7 y 15 dígitos. "
                                "Ejemplo válido: 3001234567."
                            )

    def _format_phone(self, phone):
        """
        Formatea un número de teléfono colombiano agregando un espacio después de los tres primeros dígitos.
        """
        phone_cleaned = phone.replace(" ", "")
        if len(phone_cleaned) == 10 and phone_cleaned.isdigit():
            return f"{phone_cleaned[:3]} {phone_cleaned[3:]}"
        return None
