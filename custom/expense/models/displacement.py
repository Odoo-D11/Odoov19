# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError
from datetime import timedelta, date
from holidays import country_holidays


class ExpenseDisplacement(models.Model):
    _name = 'expense.displacement'
    _description = 'Desplazamiento'
    _rec_name = 'display_name'
    _order = 'initial_date desc, id desc'

    """ONE2MANY"""
    service_line_ids = fields.One2many(
        'expense.service.line', 'displacement_id', string='Servicios')
    """MANY2ONE"""
    expense_id = fields.Many2one(
        'expense.expense', string='Gasto', required=True, ondelete='cascade', readonly=True)
    ticket_id = fields.Many2one('expense.type.ticket', string='Tiquete',)
    origin_id = fields.Many2one('res.city', string='Origen', required=True)
    destination_id = fields.Many2one(
        'res.city', string='Destino', required=True)
    category_id = fields.Many2one(
        'expense.category', string='Categoría de gasto', required=True, related='expense_id.category_id', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, default=lambda self: self.env.company.currency_id.id, readonly=True)
    """DATE"""
    initial_date = fields.Datetime(string='Fecha de inicio', required=True)
    final_date = fields.Datetime(string='Fecha de finalización', )
    """SELECTION"""
    modality_type = fields.Selection([
        ('one_way', 'Solo ida'),
        ('round_trip', 'Ida y vuelta'),
    ], string='Modalidad', )
    """MONETARY"""
    total = fields.Monetary(
        currency_field='currency_id', string='Total', compute='_compute_total', store=True)
    """CHAR"""
    display_name = fields.Char(
        string='Descripción', compute='_compute_display_name')

    @api.depends('origin_id', 'destination_id',
                 'initial_date', 'final_date',
                 'service_line_ids', 'service_line_ids.unit_price', 'service_line_ids.quantity')
    def _compute_display_name(self):
        for record in self:
            # Ciudades
            city = ''
            if record.origin_id and record.destination_id:
                if record.origin_id.id == record.destination_id.id:
                    city = record.origin_id.name
                else:
                    city = '{} - {}'.format(record.origin_id.name,
                                            record.destination_id.name)
            elif record.origin_id:
                city = record.origin_id.name
            elif record.destination_id:
                city = record.destination_id.name

            # Fechas
            def _fmt_dt(dt):
                if not dt:
                    return None
                return fields.Datetime.to_datetime(dt).strftime('%d/%m/%Y')

            start = _fmt_dt(record.initial_date)
            end = _fmt_dt(record.final_date)
            date_str = ''
            if start and end:
                date_str = '({} - {})'.format(start, end)
            elif start:
                date_str = '({})'.format(start)
            elif end:
                date_str = '({})'.format(end)

            # Total (suma de servicios: unit_price * quantity)
            total_val = 0
            for line in record.service_line_ids:
                total_val += (line.unit_price or 0) * (line.quantity or 0)

            def _format_colombian_currency(val):
                try:
                    intval = int(round(val))
                except Exception:
                    intval = 0
                return '{:,}'.format(intval).replace(',', '.')

            total_str = ''
            if record.service_line_ids:
                total_str = '$ {}'.format(
                    _format_colombian_currency(total_val))

            # display_name: "Ciudad: ... | Dia: (...) | Total: $ ..."
            parts = []
            if city:
                parts.append('Ciudad: {}'.format(city))
            if date_str:
                parts.append('Dia: {}'.format(date_str))
            if total_str:
                parts.append('Total: {}'.format(total_str))

            record.display_name = ' | '.join(
                parts) if parts else 'Desplazamiento'
            
    @api.depends('service_line_ids', 'service_line_ids.unit_price', 'service_line_ids.quantity')
    def _compute_total(self):
        for record in self:
            total_val = 0
            for line in record.service_line_ids:
                total_val += (line.unit_price or 0) * (line.quantity or 0)
            record.total = total_val

    @api.onchange('modality_type')
    def _onchange_modality_type(self):
        if self.modality_type == 'one_way':
            self.final_date = False

    @api.constrains('service_line_ids')
    def _check_service_line_ids(self):
        for record in self:
            if record.category_id.name == 'Viáticos (Alimentación, Hospedaje, etc.)':
                if not record.service_line_ids:
                    raise ValidationError(
                        _('Debe asignar al menos un servicio al desplazamiento. Por favor, verifique e intente nuevamente.'))
                for line in record.service_line_ids:
                    # Validar precio unitario y cantidad
                    if not line.unit_price or line.unit_price <= 0:
                        raise ValidationError(
                            _('Cada servicio debe tener un precio unitario válido mayor a cero.'))
                    if not line.quantity or line.quantity <= 0:
                        raise ValidationError(
                            _('Cada servicio debe tener una cantidad válida mayor a cero.'))
            else:
                if record.service_line_ids:
                    raise ValidationError(
                        _('Los desplazamientos no deben tener servicios asignados. Por favor, verifique e intente nuevamente.'))

    @api.constrains('initial_date', 'final_date', 'category_id', 'expense_id')
    def _check_dates(self):
        for record in self:
            # --- Helpers ---
            def to_date(dt):
                return fields.Datetime.to_datetime(dt).date() if dt else None

            def is_business_day(d: date) -> bool:
                # L-V y no festivo (observed=True aplica traslados por Ley Emiliani)
                if d.weekday() >= 5:
                    return False
                return d not in country_holidays("CO", years=d.year, observed=True)

            def add_business_days_inclusive(start: date, n_inclusive: int) -> date:
                """Devuelve la fecha que corresponde al 'n'-ésimo día hábil
                contando desde 'start'. Si 'start' no es hábil, comienza a contar
                desde el siguiente día hábil."""
                if n_inclusive <= 1:
                    # si piden 1 día (incluyendo creación) => devolver el primer hábil >= start
                    d = start
                    while not is_business_day(d):
                        d += timedelta(days=1)
                    return d
                # contar el 1er día hábil (>= start)
                d = start
                count = 0
                while count < n_inclusive:
                    if is_business_day(d):
                        count += 1
                        if count == n_inclusive:
                            return d
                    d += timedelta(days=1)

            # --- Fechas base (normalizadas a date) ---
            initial_date = to_date(record.initial_date)
            final_date = to_date(record.final_date)

            # Orden de fechas
            if initial_date and final_date and initial_date > final_date:
                raise ValidationError(
                    _('La fecha de inicio no puede ser posterior a la fecha de finalización.'))

            # Regla de “mínimo de días por categoría” (ignorando fines de semana/festivos)
            if record.category_id and record.expense_id and record.expense_id.creation_date and initial_date:
                creation_date = fields.Date.to_date(
                    record.expense_id.creation_date)

                # Permisos
                user = record.env.user
                is_finance = user.has_group('expense.group_accounting_expense') or user.has_group(
                    'expense.group_treasury_expense')

                if not is_finance:
                    # Define los mínimos **incluyendo el día de creación** (en días hábiles)
                    total_days_inclusive = 0
                    category_name_msg = record.category_id.display_name

                    if record.category_id.name == 'Viáticos (Alimentación, Hospedaje, etc.)':
                        # "mínimo 2 días contando el día de creación" => 2 días HÁBILES inclusivos
                        total_days_inclusive = 2
                        category_name_msg = 'Viáticos'
                    elif record.category_id.name == 'Tiquetes y vuelos':
                        # "mínimo 2 días contando el día de creación" => 2 días HÁBILES inclusivos
                        total_days_inclusive = 2
                        category_name_msg = 'Tiquetes'

                    if total_days_inclusive > 0:
                        min_allowed_date = add_business_days_inclusive(
                            creation_date, total_days_inclusive)
                        if initial_date < min_allowed_date:
                            raise ValidationError(_(
                                'Para la categoría %s, la fecha de inicio debe ser al menos %d día(s) hábiles '
                                'contando desde la fecha de creación (%s). La fecha mínima permitida es: %s'
                            ) % (
                                category_name_msg,
                                total_days_inclusive,
                                creation_date.strftime('%d/%m/%Y'),
                                min_allowed_date.strftime('%d/%m/%Y'),
                            ))

            # Solapamientos (igual que antes; opcional optimizar con limit=1)
            if record.expense_id and initial_date and final_date:
                start_dt = fields.Datetime.to_datetime(record.initial_date).replace(
                    hour=0, minute=0, second=0, microsecond=0)
                end_dt = fields.Datetime.to_datetime(record.final_date).replace(
                    hour=23, minute=59, second=59, microsecond=999999)

                overlapping = self.env['expense.displacement'].search([
                    ('expense_id', '=', record.expense_id.id),
                    ('id', '!=', record.id),
                    ('initial_date', '<=', end_dt),
                    ('final_date', '>=', start_dt),
                ], limit=1)

                if overlapping:
                    # Si quieres sugerir “día siguiente permitido”, calcula el fin máximo:
                    all_overlaps = self.env['expense.displacement'].search([
                        ('expense_id', '=', record.expense_id.id),
                        ('id', '!=', record.id),
                        ('initial_date', '<=', end_dt),
                        ('final_date', '>=', start_dt),
                    ])
                    last_end = max(d.final_date.date() for d in all_overlaps)
                    min_allowed = (last_end + timedelta(days=1)
                                   ).strftime('%d/%m/%Y')
                    raise ValidationError(_(
                        'Ya existe otro desplazamiento que coincide con las fechas seleccionadas: '
                        'Desplazamiento existente: %s - %s. Fecha mínima permitida para el nuevo desplazamiento: %s.'
                    ) % (
                        overlapping.initial_date.date().strftime('%d/%m/%Y'),
                        overlapping.final_date.date().strftime('%d/%m/%Y'),
                        min_allowed
                    ))

    def _notify_timeline_update(self, expense_ids=None, reason="update"):
        """Envía una notificación al bus para actualizar el widget timeline."""
        expense_ids = set(expense_ids or self.mapped('expense_id').ids)
        expense_ids.discard(False)
        if not expense_ids:
            return

        timestamp = fields.Datetime.now()
        bus = self.env['bus.bus']
        for expense_id in expense_ids:
            channel = f"expense_timeline_{expense_id}"
            bus._sendone(
                channel,
                "expense.timeline/update",
                {
                    "expense_id": expense_id,
                    "reason": reason,
                    "timestamp": timestamp,
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_timeline_update(reason="create")
        return records

    def write(self, vals):
        """NO PERMITE HACER CAMBIOS SI EL ESTADO DEL GASTO ES DIFERENTE A 'DRAFT'."""
        admin = self.env.user.has_group('expense.group_manager_expense')
        if not admin:
            for displacement in self:
                if displacement.expense_id.state != 'draft':
                    raise UserError(
                        _('No se pueden realizar cambios en un desplazamiento cuando la solicitud no está en estado Borrador. Por favor, verifique e intente nuevamente.'))
        res = super(ExpenseDisplacement, self).write(vals)
        if res:
            self._notify_timeline_update(reason="write")
        return res

    def unlink(self):
        expense_ids = self.mapped('expense_id').ids
        res = super(ExpenseDisplacement, self).unlink()
        if res and expense_ids:
            self.env['expense.displacement']._notify_timeline_update(
                expense_ids=expense_ids,
                reason="unlink"
            )
        return res
