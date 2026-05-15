
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PurchaseEnterprise(models.Model):
    _name = "purchase.enterprise"
    _description = "Empresa"
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    """ONE2MANY"""
    purchase_order_ids = fields.One2many(
        "purchase.management.order", "enterprise_id", string="Órdenes de Compra")
    """MANY2ONE"""
    identification_type_id = fields.Many2one(
        'identification.type', string='Tipo de identificación', required=True, domain="[('name', '=', 'NIT')]", default=lambda self: self.env['identification.type'].search([('name', '=', 'NIT')], limit=1))
    city_id = fields.Many2one('res.city', string='Ciudad', )
    state_id = fields.Many2one('res.country.state', string='Departamento', )
    country_id = fields.Many2one('res.country', string='País', default=lambda self: self.env['res.country'].search(
        [('name', '=', 'Colombia')], limit=1).id)
    """CHAR"""
    name = fields.Char(string="Nombre", required=True)
    vat = fields.Char(string="Número de identificación", required=True)
    """CHAR"""
    address = fields.Char(string="Dirección")
    email = fields.Char(string="Correo electrónico",)
    color = fields.Char(string="Color", default="#000000")
    """IMAGE"""
    logo = fields.Image(string="Logotipo", max_width=1200, max_height=1200)

    @api.model
    def init(self):
        city = self.env['res.city'].search([('name', '=', 'Bogota')], limit=1)
        nit = self.env['identification.type'].search(
            [('name', '=', 'NIT')], limit=1)
        if not nit:
            return
        required_enterprise = [
            {
                "name": 'Tsg The It Experts Sas',
                "vat": '900.994.724',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#02143f'
            },
            {
                "name": 'Novacom Net Sas',
                "vat": '901.158.055',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@novacom.net.co',
                "color": '#343f93'
            },
            {
                "name": 'Knox It Sas',
                "vat": '901.157.678',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@it4u.com.co',
                "color": '#178e9b'
            },
            {
                "name": 'UT Movilidad Tecnológica',
                "vat": '901.632.739',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#4871ec'
            },
            {
                "name": 'UT Salud',
                "vat": '901.665.809',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#10adaf'
            },
            {
                "name": 'It Business Talent Sas',
                "vat": '901.670.019',
                "identification_type_id": nit.id,
                "address": 'Av Cll 26 96j 66 OF 215',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#4d867c'
            },
            {
                "name": 'UT Tecnologías Integradas 2023',
                "vat": '901.759.772',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#0d2639'
            },
            {
                "name": 'Union Temporal H&T 2023',
                "vat": '901.784.689',
                "identification_type_id": nit.id,
                "address": 'Cll 98 70 91 OF 202',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co, facturasutht2023@recepcion.alegra.com',
            },
            {
                "name": 'Kreivo Sas',
                "vat": '901.688.058',
                "identification_type_id": nit.id,
                "address": 'Cll 93b 13 91 OF 301',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#4613ba'
            },
            {
                "name": 'UT Alcaldia Bogota 2024',
                "vat": '901.885.655',
                "identification_type_id": nit.id,
                "address": 'Cll 93b 13 91 OF 301',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#32618b'
            },
            {
                "name": 'UT SCB 2024 - Buenaventura',
                "vat": '901.900.132',
                "identification_type_id": nit.id,
                "address": 'Cll 19e 6 90 Brr El Tabor',
                "city_id": self.env['res.city'].search([('name', '=', 'Buenaventura')], limit=1).id,
                "state_id": self.env['res.country.state'].search([('name', '=', 'Valle del Cauca')], limit=1).id,
                "country_id": self.env['res.country'].search([('name', '=', 'Colombia')], limit=1).id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#183263'
            },
            {
                "name": 'UT SCJ 2024 - Jamundi',
                "vat": '901.900.116',
                "identification_type_id": nit.id,
                "address": 'Av Circunvalar Cr 4 6 50 Ca 79 Ca Conjunto Residencial San Cayetano',
                "city_id": self.env['res.city'].search([('name', '=', 'Jamundi')], limit=1).id,
                "state_id": self.env['res.country.state'].search([('name', '=', 'Valle del Cauca')], limit=1).id,
                "country_id": self.env['res.country'].search([('name', '=', 'Colombia')], limit=1).id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#767cd6'
            },
            {
                "name": 'Consorcio Llano Seguro 2024',
                "vat": '901.900.442',
                "identification_type_id": nit.id,
                "address": 'Cr 20 6 45 OF 313',
                "city_id": self.env['res.city'].search([('name', '=', 'Yopal')], limit=1).id,
                "state_id": self.env['res.country.state'].search([('name', '=', 'Casanare')], limit=1).id,
                "country_id": self.env['res.country'].search([('name', '=', 'Colombia')], limit=1).id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#ffe57d'
            },
            {
                "name": 'UT Servicios Global TIC 2024',
                "vat": '901.922.318',
                "identification_type_id": nit.id,
                "address": 'Cll 93b 13 44 P 2',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
            },
            {
                "name": 'UT Ciberseguridad T&E 2024',
                "vat": '901.901.500',
                "identification_type_id": nit.id,
                "address": 'Cll 93b 13 91 OF 301',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
            },
            {
                "name": 'Ut Gestión Integral Centro De Datos 2025',
                "vat": '901.987.496',
                "identification_type_id": nit.id,
                "address": 'Cll 93b 13 91 OF 301',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#1d74da'
            },
            {
                "name": 'UT Seguridad Electrónica Palacio',
                "vat": '902.021.309',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#545978'
            },
            {
                "name": 'UT Seguridad Ibague',
                "vat": '902.014.689',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#104c99'
            },
            {
                "name": 'UT Centro de Datos 2025',
                "vat": '902.021.939',
                "identification_type_id": nit.id,
                "address": 'Cra 98 25g 10 bodega 5',
                "city_id": city.id,
                "state_id": city.state_id.id,
                "country_id": city.state_id.country_id.id,
                "email": 'facturas.proveedores@tsg.net.co',
                "color": '#1d74da'
            }
        ]
        for enterprise_data in required_enterprise:
            if not self.search([('name', '=', enterprise_data["name"])]):
                self.with_context(tracking_disable=True).create(enterprise_data)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self.search([('name', '=', vals.get('name'))]):
                raise ValidationError(
                    _("La empresa '%s' ya existe.") % vals.get('name'))
        return super().create(vals_list)

    @api.model
    def default_get(self, fields_list):
        res = super(PurchaseEnterprise, self).default_get(fields_list)
        res['address'] = 'Cra 98 25g 10 bodega 5'
        res['city_id'] = self.env['res.city'].search(
            [('name', '=', 'Bogota')], limit=1).id
        res['state_id'] = self.env['res.country.state'].search(
            [('name', '=', 'Bogotá')], limit=1).id
        return res

    @api.constrains('vat')
    def _check_vat(self):
        for record in self:
            if record.vat.count('.') < 2 or '..' in record.vat:
                raise ValidationError(
                    _(f"El NIT '{record.vat}' no cumple con el formato esperado. El NIT debe contener al menos dos puntos ('.'), "
                      "y estos no deben estar consecutivos. Revisa el formato y corrige los errores antes de guardar.")
                )
            if record.vat.count('-') > 1 or record.vat.endswith('-'):
                raise ValidationError(
                    _(f"El NIT '{record.vat}' contiene un formato incorrecto. Solo se permite un guion ('-') en el NIT, y este no puede estar al final. "
                      "Por favor, corrige el formato del NIT para continuar."))

    @api.onchange('city_id')
    def _onchange_city_id(self):
        """Actualiza el campo state_id según la ciudad seleccionada"""
        if self.city_id:
            self.state_id = self.city_id.state_id
            self.country_id = self.city_id.state_id.country_id
        else:
            self.state_id = False
            self.country_id = False

    @api.onchange('state_id')
    def _onchange_state_id(self):
        """Resetea el campo city_id si el departamento seleccionado no coincide con la ciudad"""
        if self.state_id and self.city_id and self.city_id.state_id != self.state_id:
            self.city_id = False

    @api.constrains('city_id', 'state_id')
    def _check_city_state_consistency(self):
        for record in self:
            if record.city_id and record.state_id and record.city_id.state_id != record.state_id:
                raise ValidationError(
                    _(f"La ciudad '{record.city_id.name}' no pertenece al departamento '{record.state_id.name}'. "
                      "Por favor, selecciona una ciudad que corresponda al departamento elegido.")
                )
