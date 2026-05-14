
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, RedirectWarning
from ..utils.utils import convert_first_letter_to_uppercase


class AnalyticalAccount(models.Model):
    _name = 'analytical.account'
    _description = 'Cuenta Analítica'
    _rec_name = 'name'
    _order = 'code ASC'

    """ONE2MANY"""
    cost_center_ids = fields.One2many(
        'cost.center', 'analytical_account_id', string='Centro de Costos')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    description = fields.Char(string='Descripción')
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)

    @api.model
    def init(self):
        # Obtenemos los códigos ya existentes
        existing_codes = self.search([]).mapped('code')

        # Definimos todos los registros que queremos asegurar
        required_records = [
            {'code': '01', 'name': 'Mano de Obra',
             'description': 'Sueldos, prestaciones sociales, honorarios fijos mensuales, beneficios a empleados.'},
            {'code': '02', 'name': 'Gastos administrativos',
             'description': 'Papelería, servicios públicos, arrendamientos, software contable, líneas telefónicas, imprevistos.'},
            {'code': '03', 'name': 'Bodega',
             'description': 'Costo transversal entre el área de abastecimiento y el área contable.'},
            {'code': '04', 'name': 'Sede Medellín',
             'description': 'Gastos asociados a la sede de Medellín.'},
            {'code': '05', 'name': 'Adecuaciones',
             'description': 'Acondicionamiento de las instalaciones o sedes.'},
            {'code': '06', 'name': 'Viáticos',
             'description': 'Transporte, alimentación y hospedaje de técnicos o personal en campo.'},
            {'code': '10', 'name': 'Consultoría',
             'description': 'Asesorías en infraestructura TI, estudios de viabilidad técnica, diagnóstico de redes, etc.'},
            {'code': '41', 'name': 'Servicios de Operación',
             'description': 'Instalación, servicios temporales, soporte en campo.'},
            {'code': '42', 'name': 'Suministro de Equipos',
             'description': 'Compra de equipos propios para el proyecto.'},
            {'code': '43', 'name': 'Logística',
             'description': 'Transporte de equipos, entregas, coordinación de rutas, fletes.'},
            {'code': '44', 'name': 'Correctivos',
             'description': 'Reparaciones por fallas técnicas.'},
            {'code': '45', 'name': 'Preventivos',
             'description': 'Mantenimiento programado de equipos según historiales de cliente.'},
            {'code': '46', 'name': 'Suministro de materiales',
             'description': 'Compra de herramientas y materiales del proyecto.'},
            {'code': '47', 'name': 'Licenciamiento',
             'description': 'Licencias de software y servicios de seguridad informática.'},
            {'code': '48', 'name': 'Obra civil',
             'description': 'Obras civiles de infraestructura contempladas en el proyecto.'},
            {'code': '49', 'name': 'Garantía',
             'description': 'Servicios pos-entrega cubiertos por garantía, reposiciones.'},
        ]

        # Filtramos los que aún no existen
        to_create = [
            vals for vals in required_records if vals['code'] not in existing_codes]

        # Creamos los registros faltantes
        for vals in to_create:
            self.create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'description' in vals and vals['description']:
                vals['description'] = convert_first_letter_to_uppercase(
                    vals['description'])
        return super(AnalyticalAccount, self).create(vals_list)

    def write(self, vals):
        if 'description' in vals and vals['description']:
            vals['description'] = convert_first_letter_to_uppercase(
                vals['description'])
        return super(AnalyticalAccount, self).write(vals)

    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not rec.code.isdigit() or len(rec.code) != 2:
                raise ValidationError(
                    _('El código debe ser un número de dos dígitos. Verifique e intente de nuevo.'))
            existing = self.search(
                [('code', '=', rec.code), ('id', '!=', rec.id)], limit=1)
            if existing:
                raise ValidationError(
                    _('El código %s ya está en uso en la categoría "%s". Verifique e intente de nuevo.') % (rec.code, existing.name))

