# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import string
from odoo.exceptions import ValidationError
from rapidfuzz import fuzz
import re

from ..utils.utils import normalize_string, similar, convert_first_letter_to_uppercase


class InheritedResPartner(models.Model):
    _inherit = 'res.partner'

    """MANY2ONE"""
    identification_type_id = fields.Many2one(
        'identification.type', string='Tipo de identificación', required=True)
    city_id = fields.Many2one('res.city', string='Ciudad', )
    """CHAR"""
    normalized_name = fields.Char(
        string='Nombre normalizado', compute='_compute_normalized_name', index=True, store=True)
    display_name = fields.Char(string='Nombre para mostrar', compute='_compute_display_name')
    """BOOLEAN"""
    is_business = fields.Boolean(string='Empresa', default=False)
    is_employee = fields.Boolean(string='Empleado', default=False)

    @api.depends('name', 'is_business', 'is_employee')
    def _compute_display_name(self):
        for record in self:
            if record.is_business and not record.is_employee:
                record.display_name = record.name
            elif record.is_employee and not record.is_business:
                record.display_name = f"{record.parent_id.name}, {record.name}" if record.parent_id else record.name
            else:
                record.display_name = record.name


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self.env.context.get('skip_tz_validation'):
                continue
            normalized_name = normalize_string(vals.get('name', ' '))
            self._validate_unique_name(normalized_name)
            if 'street' in vals:
                vals['street'] = convert_first_letter_to_uppercase(
                    vals['street'])
            if 'email' in vals:
                vals['email'] = vals['email'].lower(
                ) if vals['email'] else False
            if 'city_id' in vals or 'state_id' in vals:
                city_id = vals.get('city_id')
                state_id = vals.get('state_id')
                if not self.env['res.city'].search([('id', '=', city_id), ('state_id', '=', state_id)]):
                    raise ValidationError(
                        'La ciudad no corresponde al departamento seleccionado, por favor verifique e intente nuevamente.')
            if vals.get('is_employee') and vals.get('is_business'):
                raise ValidationError(
                    'No puede seleccionar empleado y empresa al mismo tiempo, por favor verifique e intente nuevamente.')
            contact_types = [vals.get('is_employee'), vals.get('is_business')]
            if hasattr(self, 'is_supplier'):
                """SE USA PARA DETECTAR SI EL CAMPO is_supplier EXISTE EN ESTE MODELO, EL CAMPO SE ENCUENTRA EN LA CARPETA 
                (PURCHASE_MANAGEMENT)"""
                contact_types.append(vals.get('is_supplier'))
            if not any(contact_types):
                raise ValidationError(
                    'Si desea agregar un contacto debe seleccionar que tipo de contacto es, por favor verifique e intente nuevamente.')
            if 'child_ids' in vals:
                if any([child for child in vals['child_ids'] if child[2].get('is_employee') == False]):
                    raise ValidationError(
                        'Para agregar un contacto desde la página de empleados, tenga en cuenta tener seleccionado el tipo de contacto como empleado, por favor verifique e intente nuevamente.')
        if vals_list and 'name' in vals_list[0]:
            vals_list[0]['name'] = self._clean_name(vals_list[0]['name'])
        return super(InheritedResPartner, self).create(vals_list)

    def write(self, vals):
        for rec in self:
            if self.env.context.get('skip_tz_validation'):
                continue
            if 'name' in vals:
                normalized_name = normalize_string(vals.get('name', rec.name))
                self._validate_unique_name(normalized_name, rec.id)
                vals['name'] = self._clean_name(vals['name'])
            if 'email' in vals:
                vals['email'] = vals['email'].lower(
                ) if vals['email'] else False
            if 'street' in vals:
                vals['street'] = convert_first_letter_to_uppercase(
                    vals['street'])
            if 'city_id' in vals or 'state_id' in vals:
                city_id = vals.get('city_id', rec.city_id.id)
                state_id = vals.get('state_id', rec.state_id.id)
                if not self.env['res.city'].search([('id', '=', city_id), ('state_id', '=', state_id)]):
                    raise ValidationError(
                        'La ciudad no corresponde al departamento seleccionado, por favor verifique e intente nuevamente.')
            if vals.get('is_employee', rec.is_employee) and vals.get('is_business', rec.is_business):
                raise ValidationError(
                    'No puede seleccionar empleado y empresa al mismo tiempo, por favor verifique e intente nuevamente.')

            # Validación flexible para tipos de contacto
            contact_types = [
                vals.get('is_employee', rec.is_employee),
                vals.get('is_business', rec.is_business)
            ]
            # Agregar otros tipos de contacto si están disponibles
            if hasattr(rec, 'is_supplier'):
                contact_types.append(vals.get('is_supplier', rec.is_supplier))

            if not any(contact_types):
                raise ValidationError(
                    'Si desea agregar un contacto debe seleccionar que tipo de contacto es, por favor verifique e intente nuevamente.')

            """if 'child_ids' in vals:
                if any([child for child in vals['child_ids'] if child[2].get('is_employee', False) == False]):
                    raise ValidationError(
                        'Para agregar un contacto desde la página de empleados, tenga en cuenta tener seleccionado el tipo de contacto como empleado, por favor verifique e intente nuevamente.')"""
        return super(InheritedResPartner, self).write(vals)

    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        """Actualiza el campo identification_type_id según el tipo de identificación de la empresa padre"""
        if self.parent_id:
            self.identification_type_id = self.parent_id.identification_type_id
            self.vat = self.parent_id.vat
            self.city_id = self.parent_id.city_id
        else:
            self.identification_type_id = False
            self.vat = False
            self.city_id = False
            self.state_id = False
            self.country_id = False
            self.street = False

    @api.onchange('city_id')
    def _onchange_city_id(self):
        """Actualiza el campo state_id según la ciudad seleccionada"""
        if self.city_id:
            self.state_id = self.city_id.state_id
        else:
            self.state_id = False

    def _fields_sync(self, values):
        """EVITA QUE SE MODIFIQUE EL NRO. DE IDENTIFICACIÓN"""
        pass

    def _validate_unique_name(self, normalized_name, exclude_id=None):
        """ELIMINA PALABRAS COMUNES ANTES DE BUSCAR CONTACTOS SIMILARES"""
        common_words = {'colombia', 'sa', 'sas', 'de'}
        normalized_name = ' '.join(
            [word for word in normalized_name.split() if word not in common_words])
        """BUSCA CONTACTOS SIMILARES"""
        self.env.cr.execute("""SELECT id, name FROM res_partner WHERE normalized_name LIKE %s""",
                            ('%' + normalized_name + '%',))
        existing_contacts = self.env.cr.fetchall()
        for contact_id, contact_name in existing_contacts:
            if exclude_id and contact_id == exclude_id:
                continue
            contact_normalized = normalize_string(contact_name)
            """COMPARA SIMILITUD ENTRE NOMBRES"""
            if fuzz.token_sort_ratio(normalized_name, contact_normalized) > 70:
                raise ValidationError(
                    _("Ya existe un contacto con un nombre similar: %s, por favor verifique e intente nuevamente.") %
                    contact_name)

    def _clean_vat(self, vat):
        return re.sub(r'[.\-\s]', '', vat)

    @api.constrains('name')
    def _check_name_duplicate(self):
        for partner in self:
            if self.env.context.get('skip_tz_validation'):
                continue
            if not partner.name:
                continue
            normalized = normalize_string(partner.name)
            if not normalized or not normalized.strip():
                continue
            duplicate = self.env['res.partner'].search([
                ('id', '!=', partner.id),
                ('normalized_name', '=', normalized),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _(f"Ya existe un contacto con el mismo nombre: '{duplicate.name}'. "
                      f"No se permiten nombres duplicados. "
                      f"Por favor, verifique e intente nuevamente.")
                )

    @api.constrains('vat', 'identification_type_id', 'child_ids')
    def _check_vat_constraints(self):
        for partner in self:
            if self.env.context.get('skip_vat_validation'):
                continue

            clean_vat = self._clean_vat(partner.vat or '')
            id_code = partner.identification_type_id.code if partner.identification_type_id else ''
            if id_code == 'NIT':
                if not (clean_vat[:1].isdigit() and clean_vat[-1:].isdigit()):
                    raise ValidationError(
                        _(f"El NIT '{partner.vat}' es inválido. El NIT debe comenzar y terminar con un número. "
                          "Asegúrate de que el formato del NIT sea correcto antes de guardar el registro.")
                    )
                if partner.vat.count('.') < 2 or '..' in partner.vat:
                    raise ValidationError(
                        _(f"El NIT '{partner.vat}' no cumple con el formato esperado. El NIT debe contener al menos dos puntos ('.'), "
                          "y estos no deben estar consecutivos. Revisa el formato y corrige los errores antes de guardar.")
                    )
                if partner.vat.count('-') > 1 or partner.vat.endswith('-'):
                    raise ValidationError(
                        _(f"El NIT '{partner.vat}' contiene un formato incorrecto. Solo se permite un guion ('-') en el NIT, y este no puede estar al final. "
                          "Por favor, corrige el formato del NIT para continuar.")
                    )
            if (partner.parent_id
                    and partner.parent_id.is_business
                    and partner.identification_type_id
                    and partner.parent_id.identification_type_id
                    and partner.identification_type_id.id == partner.parent_id.identification_type_id.id):
                parent_clean_vat = self._clean_vat(partner.parent_id.vat or '')
                if parent_clean_vat != clean_vat:
                    raise ValidationError(
                        _(f"No puedes modificar el número de identificación del registro "
                          f"'{partner.name}' directamente porque su tipo de identificación "
                          f"coincide con el de la empresa padre "
                          f"'{partner.parent_id.name}'. Si necesitas cambiar el número de "
                          f"identificación, primero debes cambiar el tipo de identificación "
                          f"(por ejemplo, a Cédula de ciudadanía) y luego ingresar tu "
                          f"número personal.")
                    )
                continue
            if not clean_vat:
                continue
            duplicates = self.env['res.partner'].search([
                ('id', '!=', partner.id),
                ('vat', '!=', False),
            ])
            for dup in duplicates:
                dup_clean_vat = self._clean_vat(dup.vat)
                if clean_vat != dup_clean_vat:
                    continue
                if (dup.parent_id and dup.parent_id.id == partner.id
                        and dup.identification_type_id
                        and partner.identification_type_id
                        and dup.identification_type_id.id == partner.identification_type_id.id):
                    continue
                if (partner.parent_id and partner.parent_id.id == dup.id
                        and partner.identification_type_id
                        and dup.identification_type_id
                        and partner.identification_type_id.id == dup.identification_type_id.id):
                    continue
                if (partner.parent_id and dup.parent_id
                        and partner.parent_id.id == dup.parent_id.id
                        and partner.identification_type_id
                        and dup.identification_type_id
                        and partner.parent_id.identification_type_id
                        and partner.identification_type_id.id == partner.parent_id.identification_type_id.id
                        and dup.identification_type_id.id == partner.parent_id.identification_type_id.id):
                    continue
                raise ValidationError(
                    _(f"El número de identificación '{partner.vat}' del registro "
                      f"'{partner.name}' ya está registrado para "
                      f"'{dup.name}' ('{dup.vat}'). "
                      f"No se permiten números de identificación duplicados. "
                      f"Por favor, verifique y corrija el dato antes de guardar.")
                )
        for partner in self:
            if partner.is_business:
                for child in partner.child_ids:
                    if child.identification_type_id == partner.identification_type_id:
                        child.with_context(skip_vat_validation=True).write({
                            'vat': partner.vat
                        })

    @api.constrains('email')
    def _check_email_constraints(self):
        # Patrón estándar para correos válidos
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        for partner in self:
            # Verificar si el contacto está vinculado a un usuario de Odoo
            linked_user = self.env['res.users'].search(
                [('partner_id', '=', partner.id)], limit=1)
            if not linked_user:
                continue  # No validamos correos para contactos sin usuario
            if not partner.email:
                raise ValidationError(
                    _(f"El campo correo electrónico es obligatorio porque el contacto"
                      f" '{partner.name}' está vinculado a un usuario que puede iniciar sesión en el sistema.")
                )
            if not re.match(email_regex, partner.email):
                raise ValidationError(
                    _(f"El correo electrónico"
                      f" '{partner.email}' no es válido. Asegúrate de que tenga el formato correcto, por ejemplo: usuario@dominio.com.")
                )
            if ' ' in partner.email:
                raise ValidationError(
                    _(f"El correo electrónico "
                      f"'{partner.email}' contiene espacios en blanco, lo cual no es permitido. Por favor, verifica la dirección de correo electrónico.")
                )
            if len(partner.email) < 5:
                raise ValidationError(
                    _(f"El correo electrónico"
                      f" '{partner.email}' es demasiado corto para ser válido. Asegúrate de que tenga al menos 5 caracteres, por favor verifica e intenta nuevamente.")
                )

    @api.constrains('phone', 'country_id')
    def _check_phone_format(self):
        for record in self:
            if record.phone:
                # Validación de patrones irreales
                # Eliminar caracteres no numéricos
                clean_phone = re.sub(r'\D', '', record.phone)
                if len(set(clean_phone)) == 1:
                    raise ValidationError(
                        "El campo Teléfono no es obligatorio. Sin embargo, si se completa, no puede estar compuesto por un solo dígito repetido. "
                        "Por ejemplo, '1111111' no es válido."
                    )
                if clean_phone in '0123456789' or clean_phone in '9876543210':
                    raise ValidationError(
                        "El campo Teléfono no es obligatorio. Sin embargo, si se completa, no puede ser una secuencia numérica simple. "
                        "Por ejemplo, '123456789' o '987654321' no son válidos."
                    )
                # Obtener el código del país asociado
                country_code = record.country_id.code.upper() if record.country_id else None

                # Validación y formato específico para Colombia
                if country_code == 'CO':
                    # Validar si el número ya está en el formato correcto (300 1234567)
                    if not re.match(r'^[0-9]{3} [0-9]{7}$', record.phone):
                        # Intentar formatear automáticamente
                        formatted_phone = self._format_phone(record.phone)
                        if not hasattr(self, 'is_supplier'):
                            if not formatted_phone:
                                raise ValidationError(
                                    "El campo Teléfono no es obligatorio. Sin embargo, si se completa, debe contener solo números y tener una longitud de 10 dígitos. "
                                    "Ejemplo válido: 3001234567."
                                )
                        else:
                            if not formatted_phone:
                                raise ValidationError(
                                    "El valor ingresado en el campo Teléfono no es válido. Para contactos en Colombia, el número debe contener solo dígitos y tener una longitud de 10 dígitos. "
                                    "Ejemplo válido: 3001234567."
                                )
                        record.phone = formatted_phone  # Actualizar el campo con el formato correcto
                else:
                    # Validación general: solo dígitos entre 7 y 15 caracteres
                    if not re.match(r'^[0-9]{7,15}$', record.phone):
                        raise ValidationError(
                            "El campo Teléfono no es obligatorio. Sin embargo, si se completa, debe contener solo números y tener una longitud entre 7 y 15 dígitos. "
                            "Ejemplo válido: 3001234567."
                        )

    def _format_phone(self, phone):
        """
        Formatea un número de teléfono colombiano agregando un espacio después de los tres primeros dígitos.
        """
        # Eliminar cualquier espacio adicional
        phone_cleaned = phone.replace(" ", "")
        # Validar que tenga exactamente 10 dígitos
        if len(phone_cleaned) == 10 and phone_cleaned.isdigit():
            # Agregar espacio después de los tres primeros dígitos
            return f"{phone_cleaned[:3]} {phone_cleaned[3:]}"
        return None  # Retornar None si no cumple con el formato

    def _clean_name(self, name):
        # Eliminar puntos
        name = re.sub(r'\.', '', name)
        # Formatear palabras entre paréntesis
        name = re.sub(r'\(([^)]+)\)',
                      lambda m: f"({m.group(1).capitalize()})", name)
        # Eliminar paréntesis de apertura sin cierre
        name = re.sub(r'\([^)]*$', '', name)
        # Unir palabras separadas por puntos
        name = re.sub(r'\s*\.\s*', '', name)
        # Convertir a mayúsculas si el nombre tiene 4 caracteres o menos
        if len(name) <= 4:
            name = name.upper()
        else:
            # Convertir a mayúsculas la primera letra de cada palabra
            name = string.capwords(name)
        return name

    @api.depends('name')
    def _compute_normalized_name(self):
        for record in self:
            record.normalized_name = normalize_string(
                record.name) if record.name else False
