# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, exceptions, SUPERUSER_ID
from odoo.exceptions import ValidationError, UserError
import string
from ..utils.utils import is_html_content_empty, format_html_to_sentence_case, get_financial_costs, is_valid_url
from markupsafe import Markup
from odoo.tools import json_default
import json
import io
import xlsxwriter


class Opportunity(models.Model):
    _name = 'opportunity'
    _description = 'Oportunidad'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reference asc'
    _rec_name = 'reference'

    """ONE2MANY"""
    lead_ids = fields.One2many(
        'opportunity', 'lead_id', string='Oportunidades', )
    assignment_ids = fields.One2many(
        'opportunity.team.assignment', 'lead_id', string='Equipo')
    activities_ids = fields.One2many(
        'opportunity.activity', 'lead_id', string='Actividades')
    document_ids = fields.One2many(
        'opportunity.document', 'lead_id', string='Documentos', )
    assessment_ids = fields.One2many(
        'financial.assessment', 'lead_id', string='Valoraciones Financieras')
    associative_figure_line_ids = fields.One2many(
        'opportunity.associative.figure.line', 'lead_id', string='Líneas de Figura Asociativa')
    business_line_ids = fields.One2many(
        'opportunity.business.line', 'lead_id', string='Líneas de negocio')
    history_ids = fields.One2many(
        'opportunity.history', 'lead_id', string='Historial de cambios')
    timesheet_ids = fields.One2many(
        'opportunity.timesheet', 'lead_id', string='Hoja de tiempos')
    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', )
    sector_id = fields.Many2one(
        'opportunity.sector', string='Sector',)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, tracking=True)
    category_id = fields.Many2one(
        'opportunity.category', string='Categoría', required=True, tracking=True)
    type_opportunity_id = fields.Many2one(
        'opportunity.type', string='Tipo de oportunidad', tracking=True,)
    percentage_id = fields.Many2one(
        'opportunity.percentage', string='Probabilidad (%)')
    enterprise_id = fields.Many2one(
        'opportunity.enterprise', string='Empresa', required=True, tracking=True)
    source_id = fields.Many2one('opportunity.source', string='Fuente', )
    associative_figure_id = fields.Many2one(
        'opportunity.associative.figure', string='Figura asociativa')
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    """CHAR"""
    reference = fields.Char(string='Referencia',
                            default='Nuevo', readonly=True, required=True)
    name = fields.Char(string='Nombre', required=True)
    link_document = fields.Char(
        string='Link de la carpeta',)
    percentage_enterprise = fields.Char(
        string='Participación de la Empresa', compute='_compute_percentage_enterprise', store=True)
    """HTML"""
    description = fields.Html(string='Descripción')
    """MONETARY"""
    budget = fields.Monetary(string='Presupuesto', currency_field='currency_id')
    expected_income = fields.Monetary(
        string='Ingreso esperado', currency_field='currency_id')
    """DATE"""
    pre_sheet_date = fields.Date(string='Fecha de Pre-pliego')
    sheet_date = fields.Date(string='Fecha de Pliego')
    deadline_pre_sale = fields.Date(string='Fecha Límite de Preventa')
    deadline_offer = fields.Date(string='Fecha Límite de Oferta')
    deadline_adjudication = fields.Date(string='Fecha Límite de Adjudicación')
    date_observation = fields.Date(string='Fecha de Observación')
    creation_date = fields.Date(
        string='Fecha de creación', default=fields.Date.today)
    """SELECTION"""
    stage = fields.Selection([
        ('draft', 'Borrador'),
        ('open', 'Abierto'),
        ('paused', 'En pausa'),
        ('in_pre_sale', 'En preventa'),
        ('pte_approval_pre_sale_leader', 'Pte. por aprobación'),
        ('pte_approval_manager', 'Pte. por aprobación'),
        ('pte_upload_offer', 'En preventa'),
        ('pte_present', 'Pte. por presentar'),
        ('presented', 'Presentado'),
        ('won', 'Ganado'),
        ('lost', 'Perdido'),
        ('cancelled', 'Cancelado'),
    ], string='Estado comercial', default='draft', required=True)
    type = fields.Selection([
        ('opportunity', 'Oportunidad'),
        ('study', 'Estudio de mercado'),
        ('pipeline', 'Pipeline'),
    ], string='Tipo',)
    stage_pre_sale = fields.Selection([
        ('unnasigned', 'Sin asignar'),
        ('in_management', 'En gestión'),
        ('paused', 'En pausa'),
        ('delivered', 'Entregado'),
        ('not_feasible', 'No viable'),
        ('cancelled', 'Cancelado'),
    ], string='Estado preventa', default='unnasigned', required=True, readonly=True)
    """BOOLEAN"""
    active = fields.Boolean(default=True, )
    assigned_pre_sales = fields.Boolean(
        string='Preventa asignada', default=False, )
    paused = fields.Boolean(string='Pausado', default=False, )
    require_associative_figure = fields.Boolean(
        string='Requiere figura asociativa', default=False)
    require_date_observation = fields.Boolean(
        string='Requiere fecha de observación', default=False)
    sheet = fields.Boolean(string='Pliego', default=False, )

    def action_export_xlsx(self):
        """Devuelve la acción para que Odoo dispare la descarga XLSX."""
        self.env.cr.execute(
            "SELECT id FROM opportunity WHERE id IS NOT NULL")
        data = {
            'ids': [row[0] for row in self.env.cr.fetchall()],
        }
        return {
            'type': 'ir.actions.report',
            'report_type': 'xlsx',
            'data': {
                'model': 'opportunity',
                'options': json.dumps(data, default=json_default),
                'output_format': 'xlsx',
                'report_name': 'Oportunidades',
            },
        }

    def get_xlsx_report(self, data, response):
        # 1) Preparamos buffer y workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        bold = workbook.add_format({'bold': True, 'align': 'center'})
        center = workbook.add_format({'align': 'center'})
        wrap = workbook.add_format({'text_wrap': True})

        # 2) Recopilar oportunidades y sus asignaciones
        opps = self.browse(data['ids'])
        # detectamos los equipos involucrados
        teams = set()
        for opp in opps:
            for a in opp.assignment_ids:
                team = a.member_id.team_id.name or 'Sin equipo'
                teams.add(team)

        # orden preferente (si existen), luego el resto alfabético
        preferred = ['Comercial', 'Licitaciones', 'Preventa']
        ordered_teams = [t for t in preferred if t in teams] + \
            sorted(teams - set(preferred))

        # 3) calcular el máximo de participantes por equipo
        max_per_team = {}
        for team in ordered_teams:
            max_per_team[team] = max(
                len([a for a in opp.assignment_ids
                     if (a.member_id.team_id.name or '') == team])
                for opp in opps
            )

        # 4) crear hoja CRM y encabezados
        crm = workbook.add_worksheet('CRM')
        crm.set_default_row(15)
        static_headers = [
            'Tipo', 'Referencia', 'Cliente', 'Nombre', 'Estado Comercial',
            'Estado Preventa', 'Presupuesto', 'Probabilidad (%)', 'Empresa',
            'Fecha Creación', 'Fecha Preventa', 'Fecha Oferta',
            'Descripción', 'Pliego', 'Tipo de Oportunidad', 'Sector'
        ]
        # escribir estáticos
        for col, title in enumerate(static_headers):
            crm.write(0, col, title, bold)
            crm.set_column(col, col, len(title) + 2)
        # escribir dinámicos: una columna por slot de cada equipo
        first_dyn = len(static_headers)
        dyn_headers = []
        for team in ordered_teams:
            for i in range(1, max_per_team[team] + 1):
                dyn_headers.append(f"{team} {i}")
        for idx, title in enumerate(dyn_headers):
            col = first_dyn + idx
            crm.write(0, col, title, bold)
            crm.set_column(col, col, len(title) + 2)

        # 5) rellenar filas por oportunidad
        for row, opp in enumerate(opps, start=1):
            # 5.1 datos estáticos
            crm.write(row, 0,
                      dict(self._fields['type'].selection)
                      .get(opp.type) or '', center)
            crm.write(row, 1, opp.reference or '', center)
            crm.write(row, 2, opp.partner_id.name or '', center)
            crm.write(row, 3, opp.name or '', center)
            crm.write(row, 4,
                      dict(self._fields['stage'].selection)
                      .get(opp.stage) or '', center)
            crm.write(row, 5,
                      dict(self._fields['stage_pre_sale'].selection)
                      .get(opp.stage_pre_sale) or '', center)
            # Formato de moneda para presupuesto
            currency_format = workbook.add_format(
                {'num_format': '"$"#,##0', 'align': 'center'})
            crm.write(row, 6, opp.budget if opp.budget else 0, currency_format)
            crm.write(row, 7, opp.percentage_id.percentage or '', center)
            crm.write(row, 8, opp.enterprise_id.name or '', center)
            crm.write(row, 9,
                      opp.creation_date.strftime('%d/%m/%Y')
                      if opp.creation_date else '', center)
            crm.write(row, 10, opp.deadline_pre_sale.strftime('%d/%m/%Y')
                      if opp.deadline_pre_sale else '', center)
            crm.write(row, 11, opp.deadline_offer.strftime('%d/%m/%Y')
                      if opp.deadline_offer else '', center)
            crm.write(row, 12,
                      Markup(opp.description).striptags(
                      ) if opp.description else '',
                      wrap)
            crm.write(row, 13, 'Pliego' if opp.sheet else 'N/A', center)
            crm.write(row, 14, opp.type_opportunity_id.name or '', center)
            crm.write(row, 15, opp.sector_id.name or '', center)

            # 5.2 datos dinámicos por equipo
            # agrupar nombres de participantes por equipo
            by_team = {}
            for a in opp.assignment_ids:
                tname = a.member_id.team_id.name or 'Sin equipo'
                by_team.setdefault(tname, []).append(
                    a.member_id.employee_id.name or ''
                )
            # rellenar cada columna dinámica
            col_idx = first_dyn
            for team in ordered_teams:
                names = by_team.get(team, [])
                for slot in range(max_per_team[team]):
                    if slot < len(names):
                        crm.write(row, col_idx, names[slot], center)
                    else:
                        crm.write(row, col_idx, 'N/A', center)
                    col_idx += 1

        # 6) cerrar y enviar
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()

    @api.model
    def default_get(self, fields_list):
        defaults = super(Opportunity, self).default_get(fields_list)
        # Asigna al usuario actual en la tabla de "assignment_ids"
        member = self.env['opportunity.team.member'].search(
            [('employee_id.user_id', '=', self.env.user.id),
             ('team_id.name', 'in', ['Comercial', 'Licitaciones', 'Gerencia'])], limit=1)
        if member:
            assignment = self.env['opportunity.team.assignment'].create({
                'member_id': member.id,
                'team_assignment_ids': [(0, 0, {
                    'team_id': member.team_id.id,
                    'role_id': self.env['opportunity.role'].search(
                        [('name', '=', 'Principal')], limit=1).id,
                    'percentage_id': self.env['opportunity.percentage'].search(
                        [('percentage', '=', '100%')], limit=1).id,
                    'member_id': member.id,
                })],
            })
            defaults['assignment_ids'] = [(4, assignment.id)]
        """else:
            raise exceptions.UserError(
                _("El usuario '%s' no está asignado a los equipos de Comercial o Licitaciones. "
                    "Por favor, contacte al administrador del sistema.") % self.env.user.name)"""
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'description' in vals and vals['description']:
                vals['description'] = format_html_to_sentence_case(
                    vals['description'])
            if 'name' in vals and vals['name']:
                vals['name'] = string.capwords(vals['name'])
        res = super(Opportunity, self).create(vals_list)
        for record in res:
            if record.type == 'pipeline':
                record.reference = self.env['ir.sequence'].next_by_code(
                    'opportunity.pipeline')
            # Tiempos (opportunity.timesheet)
            member = self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.uid)], limit=1)
            if not member:
                raise exceptions.UserError(
                    _("El usuario '%s' no está asignado a un equipo. Por favor, contacte al administrador del sistema.") % self.env.user.name)
            # Registro indicando que se ha creado un nuevo registro
            type = 'una oportunidad' if record.type == 'opportunity' else 'un estudio de mercado' if record.type == 'study' else 'un pipeline'
            record.timesheet_ids = [(0, 0, {
                'lead_id': record.id,
                'member_id': member.id,
                'description': Markup(
                    "<span> Se ha creado <span style='color: #017e84;'>%s</span> para el cliente <span style='color: #017e84;'>%s</span>.</span>"
                    % (type, str(record.partner_id.name + ' (' + record.partner_id.identification_type_id.name + '-' + record.partner_id.vat) + ')')),
                'state': 'Creado',
                'start_date': record.create_date,
                'end_date': fields.Datetime.now(),
            })]
            if record.type in ['opportunity', 'study']:
                self.env['opportunity.timesheet'].create({
                    'lead_id': record.id,
                    'member_id': member.id,
                    'description': Markup(
                        "<span style='color: #017e84;'>Esperando cargue de documentación....</span>"),
                    'state': 'Esperando cargue de documentación',
                    'start_date': record.create_date,
                })
            if record.type == 'pipeline':
                self.env['opportunity.timesheet'].create({
                    'lead_id': record.id,
                    'member_id': member.id,
                    'description': Markup(
                        "<span style='color: #017e84;'>Esperando respuesta si es requerido el equipo de preventa...</span>"),
                    'state': 'Esperando respuesta',
                    'start_date': record.create_date,
                })
        return res

    def write(self, vals):
        for record in self:
            if 'description' in vals and vals['description']:
                vals['description'] = format_html_to_sentence_case(
                    vals['description'])
            if 'name' in vals and vals['name']:
                vals['name'] = string.capwords(vals['name'])
            restricted_stages = {'won', 'lost', 'cancelled'}
            if self.env.user.id != SUPERUSER_ID and not self.env.user.has_group('opportunities.group_root_opportunities') and record.stage in restricted_stages:
                raise exceptions.UserError(
                    _("No se puede editar una oportunidad en estado "
                      "{}. Este registro está bloqueado para modificaciones.")
                    .format(dict(self._fields['stage'].selection).get(record.stage))
                )
            """if record.type:
                # Validación para partner_id
                if 'partner_id' in vals and record.partner_id and vals.get('partner_id') != record.partner_id.id:
                    raise exceptions.UserError(
                        _("No se puede modificar el cliente "
                          "si ya se ha establecido previamente. "
                          "Por favor, contacte al administrador del sistema para obtener asistencia.")
                    )
                # Validación para sector_id
                if 'sector_id' in vals and record.sector_id and vals.get('sector_id') != record.sector_id.id:
                    raise exceptions.UserError(
                        _("No se puede modificar el sector "
                          "si ya se ha establecido previamente. "
                          "Por favor, contacte al administrador del sistema para obtener asistencia.")
                    )
                # Validación para category_id
                if 'category_id' in vals and record.category_id and vals.get('category_id') != record.category_id.id:
                    raise exceptions.UserError(
                        _("No se puede modificar la categoría "
                          "si ya se ha establecido previamente. "
                          "Por favor, contacte al administrador del sistema para obtener asistencia.")
                    )
                # Validación para type_opportunity_id
                if 'type_opportunity_id' in vals and record.type_opportunity_id and vals.get('type_opportunity_id') != record.type_opportunity_id.id:
                    raise exceptions.UserError(
                        _("No se puede modificar el tipo de oportunidad "
                          "si ya se ha establecido previamente. "
                          "Por favor, contacte al administrador del sistema para obtener asistencia.")
                    )"""
        return super(Opportunity, self).write(vals)

    def unlink(self):
        for record in self:
            if not self.env.user.has_group('opportunities.group_root_opportunities') or not SUPERUSER_ID:
                # No permite eliminar un registro si la referencia es diferente de 'Nueva'
                if record.reference != 'Nuevo':
                    raise exceptions.UserError(
                        _("No se puede eliminar un registro "
                          "si ya tiene una referencia asignada. "
                            "Por favor, contacte al administrador del sistema para obtener asistencia.")
                    )
                if self.env.user.id != SUPERUSER_ID and not self.env.user.has_group('opportunities.group_root_opportunities') and record.stage not in ['draft', 'pipeline']:
                    raise exceptions.UserError(
                        _("No se puede eliminar una oportunidad en estado "
                          "{}. Este registro está bloqueado para eliminaciones.")
                        .format(dict(self._fields['stage'].selection).get(record.stage))
                    )
        return super(Opportunity, self).unlink()

    @api.constrains('name')
    def _check_name(self):
        for record in self:
            if is_html_content_empty(record.name):
                raise ValidationError(_("El campo de nombre no puede estar vacío ni contener únicamente caracteres no válidos "
                                        "Este campo es obligatorio y debe contener información válida que describa adecuadamente el contenido. "
                                        "Por favor, revise e ingrese un texto adecuado antes de continuar."
                                        ))

    @api.constrains('description')
    def _check_description(self):
        for record in self:
            if is_html_content_empty(record.description):
                raise ValidationError(_("El campo de descripción no puede estar vacío ni contener únicamente caracteres no válidos. "
                                        "Este campo es obligatorio y debe contener información válida que describa adecuadamente el contenido. "
                                        "Por favor, revise e ingrese un texto adecuado antes de continuar."
                                        ))

    @api.constrains('type_opportunity_id', 'stage', 'type')
    def _check_type_opportunity_id(self):
        # Si es pipeline no puede ser de tipo 'Estudio de mercado' o 'RFI'
        if self.type == 'pipeline':
            if self.type_opportunity_id.name in ['Estudio de mercado', 'RFI']:
                raise ValidationError(_("La oportunidad no puede ser de tipo 'Estudio de mercado' o 'RFI' si el registro es de tipo 'Pipeline'. "
                                        "Por favor, revise e ingrese un tipo de oportunidad diferente antes de continuar."
                                        ))
        if self.type_opportunity_id.name in ['Estudio de mercado', 'RFI']:
            if self.lead_id.type_opportunity_id.name in ['Estudio de mercado', 'RFI']:
                raise ValidationError(_("La oportunidad no puede ser de tipo 'Estudio de mercado' o 'RFI' si el registro de donde proviene ya tiene este tipo de oportunidad. "
                                        "Por favor, revise e ingrese un tipo de oportunidad diferente antes de continuar."
                                        ))

    @api.constrains('link_document')
    def _check_link_document(self):
        for record in self:
            if record.link_document and not is_valid_url(record.link_document):
                raise ValidationError(_("El enlace de la carpeta es inválido. "
                                        "Por favor, revise e ingrese un enlace válido antes de continuar."
                                        ))

    @api.constrains('associative_figure_line_ids', 'percentage_enterprise')
    def _check_percentage_enterprise(self):
        for record in self:
            if record.require_associative_figure:
                stake = 0
                for line in record.associative_figure_line_ids:
                    stake += int(line.percentage_id.percentage.replace('%', ''))
                if stake > 100:
                    raise ValidationError(_("La suma de las participaciones de las empresas asociadas supera el 100%. "
                                            "Por favor, revise e ingrese un porcentaje válido antes de continuar."
                                            ))
                if record.percentage_enterprise == '0%':
                    raise ValidationError(_(
                        "La empresa '{}' debe tener al menos un 1% de participación. "
                        "Por favor, revise la tabla de participantes para ajustar correctamente la distribución antes de continuar."
                    ).format(record.enterprise_id.name))

    """@api.constrains('active')
    def _check_active(self):
        if not self.active:
            if not self.env.user.has_group('opportunities.group_root_opportunities') or not SUPERUSER_ID:
                raise exceptions.UserError(
                    _("No tiene permisos para archivar este registro. "
                      "Por favor, contacte al administrador del sistema para obtener asistencia.")
                )"""

    @api.depends('require_associative_figure', 'associative_figure_line_ids.percentage_id')
    def _compute_percentage_enterprise(self):
        for record in self:
            if record.require_associative_figure:
                stake = 0
                for line in record.associative_figure_line_ids:
                    stake += int(line.percentage_id.percentage.replace('%', ''))
                record.percentage_enterprise = str(100 - stake) + '%'
            else:
                record.percentage_enterprise = '100%'

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            self.sector_id = self.category_id.sector_id.id
            self.type_opportunity_id = False if self.type in [
                'opportunity', 'study'] else self.type_opportunity_id.id

    @api.onchange('type_opportunity_id')
    def _onchange_type_opportunity_id(self):
        if self.type_opportunity_id and self.reference == 'Nuevo' and self.type != 'pipeline':
            if self.type_opportunity_id.name in ['Estudio de mercado', 'RFI']:
                self.type = 'study'
            else:
                self.type = 'opportunity'

    @api.onchange('require_associative_figure')
    def _onchange_require_associative_figure(self):
        if not self.require_associative_figure:
            self.associative_figure_id = False
            self.associative_figure_line_ids = [(5, 0, 0)]

    """TIEMPOS"""

    def action_record_timesheet(self):
        return {
            'name': _('Odoo'),
            'type': 'ir.actions.act_window',
            'res_model': 'opportunity',
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
            'views': [(self.env.ref('opportunities.wizard_opportunity_form_view_timesheet').id, 'form')],
        }

    """CREAR ACTIVIDAD"""

    def action_record_activities(self):
        member = self.env['opportunity.team.member'].search(
            [('employee_id.user_id', '=', self.env.user.id)], limit=1)
        if not member:
            raise exceptions.UserError(
                _("El usuario '%s' no está asignado a un equipo. Por favor, contacte al administrador del sistema.") % self.env.user.name)
        if self.id:
            domain = [('member_id', '=', member.id), ('lead_id', '=', self.id)]
            context = {'default_partner_id': self.partner_id.id,
                       'default_member_id': member.id,
                       'default_lead_id': self.id,
                       'default_requires_lead_id': True,
                       }
        else:
            domain = []
            context = {'search_default_assigned_to_me': 1}
        return {
            'name': _('Actividades'),
            'type': 'ir.actions.act_window',
            'res_model': 'opportunity.activity',
            'view_mode': 'list,form',
            'domain': domain,
            'context': context,
            'target': 'current',
        }

    """ESTABLECER PREVENTA REQUERIDA (PIPELINE)"""

    def action_set_pre_sale_required(self):
        views = [
            (self.env.ref('opportunities.view_pre_sale_required_form').id, 'form')]
        if self.type == 'pipeline' and self.stage == 'open':
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'opportunity.pre.sale.required',
                'view_mode': 'form',
                'views': views,
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                }
            }
        else:
            raise ValidationError(
                _('No se puede establecer una oportunidad como "Requiere preventa" si no está en estado abierto.'))

    """ABRIR LA DOCUMENTACIÓN"""

    def action_open_documentation(self):
        return {
            'type': 'ir.actions.act_url',
            'url': self.link_document,
            'target': 'new',
        }

    """CARGAR DOCUMENTACIÓN"""

    def action_upload_documentation(self):
        if self.stage == 'draft' and self.type_opportunity_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity.upload.document',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se pueden subir documentos a una oportunidad que no esté en estado borrador o que no tenga un tipo de oportunidad asignado.'),
                    'type': 'danger',
                    'sticky': False,

                }
            }

    """CAMBIAR A PLIEGO"""

    def action_change_to_sheet(self):
        # if self.stage in ['draft', 'open', 'in_pre_sale', 'pte_approval_pre_sale_leader', 'pte_approval_manager']:
        self.sheet = True
        """msg = Markup(
            "<span>La oportunidad ha sido marcado como <span style='color: #017e84;'>Pliego</span>.</span>")
        self.message_post(body=msg)"""
        """else:
            raise ValidationError(
                _('No se puede marcar una oportunidad como pliego si no se encuentra en estado borrador, abierto, preventa o pendiente por aprobación.'))
"""
    """ESTABLECER PREVENTA"""

    def action_assing_pre_sale_team(self):
        if self.stage == 'in_pre_sale':
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity.assign.pre.sale',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _(
                        'No es posible asignar un equipo de preventa porque la oportunidad no se encuentra en estado preventa. '
                        'Asegúrate de que la oportunidad esté en la etapa correcta antes de realizar esta acción.'
                    ),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    """DEVOLVER A COMERCIAL"""

    def action_return_to_commercial(self):
        if self.stage in ['in_pre_sale', 'pte_upload_offer', 'presented']:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity.return',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _(
                        'No es posible devolver la oportunidad a comercial porque la oportunidad no se encuentra en estado preventa o presentada. '
                        'Asegúrate de que la oportunidad esté en la etapa correcta antes de realizar esta acción.'
                    ),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    """DEVOLVER A PREVENTA"""

    def action_return_to_pre_sale(self):
        self.stage = 'in_pre_sale'
        # Tiempos (opportunity.timesheet)
        member = self.env['opportunity.team.member'].search(
            [('employee_id.user_id', '=', self.env.uid)], limit=1)
        if not member:
            raise exceptions.UserError(
                _("El usuario '%s' no está asignado a un equipo. Por favor, contacte al administrador del sistema.") % self.env.user.name)
        wait = self.env['opportunity.timesheet'].search(
            [('lead_id', '=', self.id), ('state', '=', 'Esperando respuesta de comercial')], limit=1)
        if wait:
            wait.write({
                'state': 'Devuelto a preventa',
                'description': Markup(
                    "<span>Se <span style='color: #017e84'>devuelve</span> el registro a preventa.</span>"
                ),
                'end_date': fields.Datetime.now(),
            })
            if not self.assigned_pre_sales:
                self.env['opportunity.timesheet'].sudo().create({
                    'lead_id': self.id,
                    'member_id': member.id,
                    'description': Markup(
                        f"<span style='color: #017e84;'>Esperando asignación de el equipo de preventa...</span>"
                    ),
                    'state': 'Esperando asignación equipo de preventa',
                    'start_date': fields.Datetime.now(),
                })
            else:
                self.env['opportunity.timesheet'].sudo().create({
                    'lead_id': self.id,
                    'member_id': member.id,
                    'description': Markup(
                        f"<span style='color: #017e84;'>Esperando MVF - Valoración financiera...</span>"
                    ),
                    'state': 'Esperando MVF - Valoración financiera',
                    'start_date': fields.Datetime.now(),
                })

    """CANCELAR OPORTUNIDAD"""

    def action_cancel_opportunity(self):
        if self.stage not in ['won', 'lost', 'cancelled', 'draft']:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity.cancel',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _(
                        'Verifique que el registro no se encuentre en los siguientes estados: '
                        '[ Ganado, Perdido, Cancelado, No Presentado, Borrador ]. '
                        'No es posible cancelar una oportunidad en estos estados, '
                        'por favor, verifique el estado actual del registro antes de continuar.'
                    ),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    """ADJUNTAR MVF - VALORACIÓN FINANCIERA"""

    def action_add_financial_assessment(self):
        # if self.stage in ['in_pre_sale', 'presented'] or self.reference not in ['EDM', 'PIP']:
        return {
            'type': 'ir.actions.act_window',
            'name': 'Odoo',
            'res_model': 'upload.financial.assessment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_partner_id': self.partner_id.id,
            }
        }
        """else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _(
                        'No es posible adjuntar una valoración financiera a una oportunidad que no se encuentre en estado preventa, presentada o que sea de tipo "Estudio de mercado". '
                        'Asegúrate de que la oportunidad esté en la etapa correcta antes de realizar esta acción.'
                    ),
                    'type': 'danger',
                    'sticky': False,
                }
            }"""

    """APROBAR VALORACIÓN FINANCIERA"""

    def action_approve_financial_assessment(self):
        if self.stage in ['pte_approval_pre_sale_leader', 'pte_approval_manager']:
            """BUSCA LA VALORACION FINANCIERA DE LA OPORTUNIDAD"""
            vf = self.env['financial.assessment'].search(
                [('lead_id', '=', self.id)], limit=1)
            if not vf:
                raise ValidationError(
                    _('No se ha encontrado una valoración financiera para esta oportunidad.'
                        'Por favor, contacte al administrador del sistema.'))
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'approve.financial.assessment',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                    'default_assessment': vf.assessment,
                }
            }

    """PAUSAR OPORTUNIDAD"""

    def action_pause_opportunity(self):
        msg = Markup(
            "<span>La oportunidad ha sido marcada como <span style='color: #017e84'>Pausada</b>."
        )
        # Tiempos (opportunity.timesheet)
        member = self.env['opportunity.team.member'].search(
            [('employee_id.user_id', '=', self.env.user.id)], limit=1)
        if not member:
            raise exceptions.UserError(
                _("El usuario '%s' no está asignado a un equipo. Por favor, contacte al administrador del sistema.") % self.env.user.name)
        state = 'Esperando asignación equipo de preventa' if not self.assigned_pre_sales else (
            'Esperando MVF - Valoración financiera' if self.type == 'opportunity' else 'Esperando cargue de oferta')
        if self.stage == 'in_pre_sale':
            wait = self.env['opportunity.timesheet'].search(
                [('lead_id', '=', self.id), ('state', '=', state)], limit=1)
            if wait:
                wait.write({
                    'state': 'Pausado',
                    'description': Markup(
                        "<span>Se <span style='color: #017e84'>pausa</span> el registro.</span>"
                    ),
                    'end_date': fields.Datetime.now(),
                })
                self.env['opportunity.timesheet'].sudo().create({
                    'lead_id': self.id,
                    'member_id': member.id,
                    'description': Markup(
                        "<span style='color: #017e84'>Esperando reanudar el proceso...</span>"
                    ),
                    'state': 'Esperando reanudar el proceso',
                    'start_date': fields.Datetime.now(),
                })
        self.sudo().stage = 'paused'
        self.sudo().stage_pre_sale = 'paused'
        self.sudo().message_post(body=msg)

    """REANUDAR OPORTUNIDAD"""

    def action_resume_opportunity(self):
        if self.stage == 'paused':
            msg = Markup(
                "<span>Se <span style='color: #017e84'>reanuda</span> el proceso de la oportunidad.</span>"
            )
            # Tiempos (opportunity.timesheet)
            member = self.env['opportunity.team.member'].search(
                [('employee_id.user_id', '=', self.env.user.id)], limit=1)
            if not member:
                raise exceptions.UserError(
                    _("El usuario '%s' no está asignado a un equipo. Por favor, contacte al administrador del sistema.") % self.env.user.name)
            wait = self.env['opportunity.timesheet'].search(
                [('lead_id', '=', self.id), ('state', '=', 'Esperando reanudar el proceso')], limit=1)
            if wait:
                wait.write({
                    'state': 'Reanudado',
                    'description': Markup(
                        "<span>Se <span style='color: #017e84'>reanuda</span> el proceso.</span>"
                    ),
                    'end_date': fields.Datetime.now(),
                })
                if not self.assigned_pre_sales:
                    self.env['opportunity.timesheet'].sudo().create({
                        'lead_id': self.id,
                        'member_id': member.id,
                        'description': Markup(
                            "<span style='color: #017e84'>Esperando asignación de el equipo de preventa...</span>"
                        ),
                        'state': 'Esperando asignación equipo de preventa',
                        'start_date': fields.Datetime.now(),
                    })
                else:
                    self.env['opportunity.timesheet'].sudo().create({
                        'lead_id': self.id,
                        'member_id': member.id,
                        'description': Markup(
                            "<span style='color: #017e84'>Esperando MVF - Valoración financiera...</span>"
                        ),
                        'state': 'Esperando MVF - Valoración financiera',
                        'start_date': fields.Datetime.now(),
                    })
            self.sudo().stage = 'in_pre_sale'
            self.sudo().stage_pre_sale = 'in_management'
            self.sudo().message_post(body=msg)

    """VER FIGURA ASOCIATIVA"""

    def action_view_associative_figure(self):
        views = [
            (self.env.ref('opportunities.opportunity_form_view_associative_figure').id, 'form')]
        if self.associative_figure_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity',
                'res_id': self.id,
                'views': views,
                'view_mode': 'form',
                'target': 'new',
                'context': dict(self.env.context, skip_associative_check=True),
            }
        else:
            raise ValidationError(
                _('Revise que el registro tenga una figura asociativa asignada. '
                  'Si el problema persiste, contacte al administrador del sistema.'))

    """CARGAR OFERTA"""

    def action_upload_offer(self):
        # if self.stage == 'pte_upload_offer' or (self.type_opportunity_id.name in ['Estudio de mercado', 'RFI'] and self.stage == 'presented'):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Odoo',
            'res_model': 'upload.offer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_edm': True if self.type_opportunity_id.name in ['Estudio de mercado', 'RFI'] else False,
            }
        }
        """else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se pueden subir una oferta a una oportunidad que no esté en estado pendiente por subir oferta.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }"""

    """PRESENTAR OPORTUNIDAD"""

    def action_present_lead(self):
        if self.stage == 'pte_present':
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'present.lead',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se puede establecer una oportunidad como presentada o no presentada si no se encuentra en estado pendiente por presentar.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    """GANAR OPORTUNIDAD"""

    def action_marked_as_won(self):
        if self.stage == 'presented' and self.type_opportunity_id.name not in ['Estudio de mercado', 'RFI']:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity.won',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': self.id,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No se puede establecer una oportunidad como ganada o perdida si no se encuentra en estado presentado.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    """CREAR OPORTUNIDAD"""

    def action_create_opportunity(self):
        views = [
            (self.env.ref('opportunities.opportunity_view_form').id, 'form')]
        if not self.lead_ids:
            lead = self.env['opportunity'].create({
                'sector_id': self.sector_id.id,
                'partner_id': self.partner_id.id,
                'category_id': self.category_id.id,
                'enterprise_id': self.enterprise_id.id,
                'source_id': self.source_id.id,
                'name': self.name,
                'description': self.description,
                'budget': self.budget,
                'lead_id': self.id,
                'type_opportunity_id': self.env['opportunity.type'].search(
                    [('name', '=', 'RFP')], limit=1).id if self.sector_id.name == 'Privado' and self.type_opportunity_id.name == 'RFI' else False,
                'stage': 'draft',
            })
            self.active = False
            return {
                'type': 'ir.actions.act_window',
                'name': 'Nueva',
                'res_model': 'opportunity',
                'view_mode': 'form',
                'target': 'current',
                'res_id': lead.id,
                'views': views,
            }
        else:
            raise ValidationError(
                _('El registro ya tiene una oportunidad asociada. Si el problema persiste, contacte al administrador del sistema.'))

    """VER OPORTUNIDAD"""

    def action_view_opportunity(self):
        views = [
            (self.env.ref('opportunities.opportunity_view_form').id, 'form')]
        if self.lead_ids:
            lead = self.env['opportunity'].search(
                [('lead_id', '=', self.id)], limit=1)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity',
                'res_id': lead.id,
                'views': views,
                'view_mode': 'form',
                'target': 'current',
            }
        elif self.lead_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Odoo',
                'res_model': 'opportunity',
                'res_id': self.lead_id.id,
                'views': views,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            raise ValidationError(
                _('No se ha encontrado un registro asociado. Si el problema persiste, contacte al administrador del sistema.'))

    """CONVERTIR PIPELINE A"""

    def action_convert_pipeline_to(self):
        if self.stage == 'presented':
            return {
                'name': _('Odoo'),
                'type': 'ir.actions.act_window',
                'res_model': 'opportunity.pipeline.to',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_lead_id': self.id},
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Solo se puede convertir un pipeline a una oportunidad o estudio de mercado si se encuentra en estado pipeline.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
