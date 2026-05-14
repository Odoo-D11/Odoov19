# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ProjectManagement(models.Model):
    _name = 'project.management'
    _description = 'Proyecto'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    """ONE2MANY"""
    cost_center_ids = fields.One2many(
        'cost.center', 'project_id', string='Centros de Costo')
    """MANY2ONE"""
    category_id = fields.Many2one(
        'project.category', string='Categoría', required=True)
    team_id = fields.Many2one(
        'project.team', string='Área responsable', required=True)
    """DATE"""
    start_date = fields.Date(string='Fecha de inicio',)
    """CORREO ELECTRÓNICO 5 DIAS ANTES AVISARLE A YENNY - ACTUALIZAR FECHAS"""
    end_date = fields.Date(string='Fecha de fin',)
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True, copy=False,)
    prefix = fields.Char(string='Prefijo', required=True,)
    display_name = fields.Char(
        string='Nombre para mostrar', compute='_compute_display_name', store=True)
    """BOOLEAN"""
    active = fields.Boolean(string='Activo', default=True)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for record in self:
            if record.code:
                record.display_name = f"{record.name} - {record.code}"
            else:
                record.display_name = record.name

    def action_create_cost_centers(self):
        if not self.code:
            raise UserError(
                'El proyecto no tiene código. Asigna un código antes de crear centros de costo.')
        analytical_accounts = self.env['analytical.account'].search(
            [('active', '=', True)])
        existing_accounts = self.cost_center_ids.mapped(
            'analytical_account_id')
        currency = self.env.company.currency_id
        vals_list = []
        for account in analytical_accounts:
            if account in existing_accounts:
                continue
            vals_list.append({
                'analytical_account_id': account.id,
                'project_id': self.id,
                'code': self.code + account.code,
                'currency_id': currency.id,
            })
        if vals_list:
            self.env['cost.center'].create(vals_list)

    def notify_accounting_team(self):
        """CODIGO PARA QUE ENVIE CORREO AL EQUIPO DE CONTABILIDAD 5 DIAS ANTES DE LA FECHA DE FIN"""
        accounting_team = self.env['project.team'].search(
            [('name', '=', 'Contabilidad')], limit=1)
        if not accounting_team:
            return
        accounting_members = self.env['project.member'].search(
            [('team_id', '=', accounting_team.id)])
        if not accounting_members:
            return
        email_template = self.env.ref(
            'project_management.email_template_project_end_date_notification')
        if not email_template:
            return
        for member in accounting_members:
            if member.employee_id and member.employee_id.work_email:
                email_template.send_mail(self.id, email_values={
                                         'email_to': member.employee_id.work_email})
