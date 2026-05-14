from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..utils.utils import is_valid_url, _clean_name
import re
import string

_LEGAL_SUFFIXES = re.compile(
    r'\b(s\.?a\.?s\.?|s\.?a\.?|ltda\.?|sas|ltda|l\.?t\.?d\.?a\.?|'
    r'inc\.?|corp\.?|llc\.?|cia\.?|co\.?|e\.?u\.?)\b',
    re.IGNORECASE
)


def _normalize_name(name):
    normalized = _LEGAL_SUFFIXES.sub('', (name or '').lower())
    return re.sub(r'\s+', ' ', normalized).strip()


class QuotationQuotation(models.Model):
    _name = 'quotation.quotation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Cotización'
    _rec_name = 'request_quotation_id'

    """ONE2MANY"""
    product_line_ids = fields.One2many(
        'product.quotation.line', 'quotation_id', string='Líneas de productos')
    observation_ids = fields.One2many(
        'purchase.management.quotation.observation', 'quotation_id', string='Observaciones')
    purchase_observation_recommendation_ids = fields.One2many(
        'purchase.project.observation.recommendation', 'quotation_id', string='Recomendaciones', readonly=True)
    commercial_term_ids = fields.One2many(
        'purchase.commercial.term', 'quotation_id', string='Condiciones Comerciales')
    """CHAR"""
    supplier_name = fields.Char(string='Proveedor', required=True)
    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de cotización', readonly=True, ondelete='cascade')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True,
        default=lambda self: self.env['res.currency'].search([('name', '=', 'COP')], limit=1))
    """DATE"""
    validity_date = fields.Date(string="Fecha de vigencia", required=True)
    delivery_date = fields.Date(string='Fecha de entrega', required=True)
    trm_date = fields.Date(string='Fecha TRM', readonly=True)
    creation_date = fields.Date(
        string='Fecha de creación', default=fields.Date.context_today, )
    """FLOAT"""
    trm = fields.Float(string='TRM', digits=(12, 2))
    total = fields.Monetary(string='Total', readonly=True,
                            currency_field='currency_id', compute='_compute_total', store=True)
    """SELECTION"""
    type = fields.Selection([('product', 'Producto'), ('service', 'Servicio'),
                            ('mix', 'Mixto')], string='Tipo', required=True, readonly=True)
    """CHAR"""
    evidence = fields.Char(string='Evidencia', required=True)
    color = fields.Char(string="Color", default="#3B82F6")
    payment_term = fields.Char(
        string='Plazo de pago', required=True, default='30 días')
    """BOOLEAN"""
    awarded = fields.Boolean(string='Adjudicado', default=False, readonly=True)
    rejected = fields.Boolean(string='Rechazado', default=False, readonly=True)

    @api.depends('product_line_ids.subtotal', 'product_line_ids.display_type')
    def _compute_total(self):
        for quotation in self:
            # Solo suma productos, no las notas
            products = quotation.product_line_ids.filtered(
                lambda l: not l.display_type)
            quotation.total = sum(products.mapped('subtotal'))

    @api.constrains('product_line_ids', 'total')
    def _check_qty_price(self):
        for quotation in self:
            if quotation.total <= 0:
                raise ValidationError(
                    _('El total de la cotización debe ser mayor a cero.'))

    @api.onchange("currency_id")
    def _onchange_currency_id(self):
        """
        Obtiene el TRM. 
        NOTA: El TRM se obtiene de la última tasa registrada en res.currency.rate para la moneda seleccionada.
        """
        for rec in self:
            rec.trm = False
            rec.trm_date = False
            if not rec.currency_id or rec.currency_id.name == "COP":
                continue
            try:
                rate = self.env['res.currency.rate'].search([
                    ('currency_id', '=', rec.currency_id.id),
                    ('company_id', '=', rec.env.company.id),
                ], order='name desc', limit=1)
                if rate:
                    rec.trm = rate.inverse_company_rate
                    rec.trm_date = rate.name
            except Exception as e:
                continue

    @api.constrains('trm', 'currency_id')
    def _check_trm(self):
        for q in self:
            if q.currency_id.name != 'COP' and q.trm <= 0:
                raise ValidationError(
                    _('El TRM debe ser mayor a cero para monedas extranjeras.'))

    @api.constrains('evidence')
    def _check_evidence(self):
        if not is_valid_url(self.evidence):
            raise ValidationError(_('El enlace de evidencia no es válido.'))

    def _notify_timeline_update(self, request_quotation_ids=None, reason="update"):
        rq_ids = set(request_quotation_ids or self.mapped(
            'request_quotation_id').ids) - {False}
        if not rq_ids:
            return
        # Notifica al sistema para que actualice la informacion en vivo para el widget(quotation_board)
        bus = self.env['bus.bus']
        timestamp = fields.Datetime.to_string(fields.Datetime.now())
        for rid in rq_ids:
            bus._sendone(f"quotation_line{rid}", "quotation.quotation/update", {
                "quotation_id": rid, "reason": reason, "timestamp": timestamp
            })

    @api.constrains('supplier_name', 'request_quotation_id')
    def _check_supplier_name(self):
        for record in self:
            if not record.request_quotation_id or not record.supplier_name:
                continue
            normalized_new = _normalize_name(record.supplier_name)
            siblings = self.search([
                ('request_quotation_id', '=', record.request_quotation_id.id),
                ('id', '!=', record.id),
            ])
            dup = siblings.filtered(
                lambda q: _normalize_name(q.supplier_name) == normalized_new
            )
            if dup:
                raise ValidationError(
                    _('El proveedor "%s" ya tiene una cotización en esta solicitud.') % record.supplier_name)

    @api.constrains('supplier_name')
    def _check_supplier_name_format(self):
        email_pattern = re.compile(r'.*@.*\..*')
        url_pattern = re.compile(r'https?://')
        for record in self:
            if not record.supplier_name:
                continue
            supplier_name = record.supplier_name.strip()
            if email_pattern.match(supplier_name):
                raise ValidationError(
                    _('El nombre del proveedor no puede ser un correo electrónico.'))
            if url_pattern.match(supplier_name.lower()):
                raise ValidationError(
                    _('El nombre del proveedor no puede ser una URL.'))
            if supplier_name.isdigit():
                raise ValidationError(
                    _('El nombre del proveedor no puede ser solo números.'))
            if len(supplier_name) < 2:
                raise ValidationError(
                    _('El nombre del proveedor debe tener al menos 2 caracteres.'))

    def _validate_unique_product_names(self):
        """Valida que productos con el mismo nombre tengan especificaciones diferentes"""
        for record in self:
            sorted_lines = list(record.product_line_ids.sorted('sequence'))
            # Crea la lista de tuplas (nombre_producto, especificacion) usando secuencia
            product_spec_pairs = []
            i = 0
            while i < len(sorted_lines):
                line = sorted_lines[i]
                if line.display_type != 'line_note':
                    # Es un producto, buscar su nota (debe ser la siguiente línea)
                    spec_text = ''
                    if i + 1 < len(sorted_lines):
                        next_line = sorted_lines[i + 1]
                        if next_line.display_type == 'line_note' and next_line.product_name == line.name:
                            spec_text = (next_line.name or '').strip().lower()
                            i += 1  # Salta la nota ya procesada
                    product_spec_pairs.append((line.name, spec_text))
                i += 1
            # Verifica que no haya pares (nombre, especificación) duplicados
            seen_pairs = set()
            for name, spec in product_spec_pairs:
                pair = (name.strip().lower() if name else '', spec)
                if pair in seen_pairs:
                    raise ValidationError(
                        _('El producto "%s" está duplicado y tiene la misma especificación. '
                          'Los productos duplicados deben tener especificaciones diferentes.') % name
                    )
                seen_pairs.add(pair)

    def _validate_products_have_specifications(self):
        """Valida que cada producto tenga exactamente una especificación (nota) asociada"""
        for record in self:
            sorted_lines = list(record.product_line_ids.sorted('sequence'))
            # Valida la estructura: cada producto debe tener su nota inmediatamente después
            i = 0
            while i < len(sorted_lines):
                line = sorted_lines[i]
                if line.display_type != 'line_note':
                    # Es un producto, verifica que la siguiente línea sea su nota
                    if i + 1 >= len(sorted_lines):
                        raise ValidationError(
                            _('El producto "%s" no tiene una especificación asociada.') % line.name
                        )
                    next_line = sorted_lines[i + 1]
                    if next_line.display_type != 'line_note':
                        raise ValidationError(
                            _('El producto "%s" no tiene una especificación asociada.') % line.name
                        )
                    if (next_line.product_name or '').strip().lower() != (line.name or '').strip().lower():
                        raise ValidationError(
                            _('La especificación después del producto "%s" está asociada a otro producto ("%s").') % (
                                line.name, next_line.product_name)
                        )
                    i += 2
                else:
                    # Es una nota sin producto previo
                    raise ValidationError(
                        _('Existe una especificación asociada al producto "%s", pero ese producto no se encuentra antes de ella en la lista.') % line.product_name
                    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group('purchase_management.group_manager_purchase_management'):
            is_member = self.env['purchase.member'].search_count([
                ('employee_id.user_id', '=', self.env.uid),
            ]) > 0
            if not is_member:
                raise UserError(
                    _('Solo los miembros del área de Compras pueden registrar cotizaciones.'))
        for vals in vals_list:
            if vals.get('supplier_name'):
                vals['supplier_name'] = _clean_name(vals['supplier_name'])
            if vals.get('payment_term'):
                vals['payment_term'] = string.capwords(
                    vals['payment_term'].strip())
        records = super().create(vals_list)
        records._notify_timeline_update(reason="create")
        return records

    def write(self, vals):
        if vals.get('supplier_name'):
            vals['supplier_name'] = _clean_name(vals['supplier_name'])
        if vals.get('payment_term'):
            vals['payment_term'] = string.capwords(
                vals['payment_term'].strip())
        if not self.env.user.has_group('purchase_management.group_manager_purchase_management') or self.env.user.has_group('purchase_management.group_unlock_request_quotation'):
            protected_fields = {'supplier_name', 'currency_id', 'payment_term', 'trm', 'observation_ids',
                                'creation_date', 'commercial_term_ids', 'validity_date', 'delivery_date',
                                'evidence', 'product_line_ids'}
            if protected_fields.intersection(vals.keys()):
                for rec in self:
                    if rec.request_quotation_id and rec.request_quotation_id.state not in ('sent', 'in_shopping'):
                        state_desc = dict(rec.request_quotation_id._fields['state'].selection).get(
                            rec.request_quotation_id.state)
                        raise UserError(
                            _('No se puede modificar la cotización cuando la solicitud está en "%s".') % state_desc)

        res = super().write(vals)
        if res:
            self._notify_timeline_update(reason="write")
            if 'product_line_ids' in vals:
                self._validate_unique_product_names()
                self._validate_products_have_specifications()
        return res

    def unlink(self):
        rq_ids = set(self.mapped('request_quotation_id').ids) - {False}
        res = super().unlink()
        if res and rq_ids:
            bus = self.env['bus.bus']
            timestamp = fields.Datetime.now()
            for rid in rq_ids:
                bus._sendone(f"quotation_line{rid}", "quotation.quotation/update", {
                    "quotation_id": rid, "reason": "unlink", "timestamp": str(timestamp)
                })
        return res
