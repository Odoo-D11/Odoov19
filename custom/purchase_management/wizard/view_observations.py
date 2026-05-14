from odoo import models, fields, api, _


class PurchaseManagementViewObservationWizardLine(models.TransientModel):
    _name = "purchase.management.view.observation.wizard.line"
    _description = "Línea de observación del asistente para ver observaciones de compras"
    _transient_max_count = 100
    _transient_max_hours = 24

    wizard_id = fields.Many2one(
        "purchase.management.view.observations.wizard", string="Asistente para ver observaciones")
    team = fields.Selection([
        ('applicant', 'Lid. de Proyecto'),
        ('final_recommendation', 'Compras'),
        ('purchase_committee', 'Comite de Compras'),
    ], string='Equipo', readonly=True)
    observation = fields.Char(string='Observación', required=True)


class PurchaseManagementViewObservationsWizard(models.TransientModel):
    _name = "purchase.management.view.observations.wizard"
    _description = "Asistente para ver observaciones de compras"
    _transient_max_count = 100
    _transient_max_hours = 24

    observation_line_ids = fields.One2many(
        'purchase.management.view.observation.wizard.line', 'wizard_id', string='Líneas de observaciones')
    quotation_id = fields.Many2one(
        'quotation.quotation', string='Cotización', required=True)
    supplier_name = fields.Char(
        string='Proveedor', related='quotation_id.supplier_name', readonly=True)
    team = fields.Selection([
        ('applicant', 'Lid. de Proyecto'),
        ('final_recommendation', 'Compras'),
        ('purchase_committee', 'Comite de Compras'),
    ], string='Equipo seleccionado')
    state = fields.Selection([
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('not_recommended', 'No Recomendado'),
        ('recommended', 'Recomendado')
    ], string='Estado', readonly=True)
    available_teams = fields.Char(
        string='Equipos disponibles', compute='_compute_available_teams')
    category = fields.Selection(
        related='quotation_id.request_quotation_id.category',
        string='Categoría',
        store=False,
    )

    @api.depends('quotation_id')
    def _compute_available_teams(self):
        """Calcula los equipos que tienen observaciones"""
        for wizard in self:
            if wizard.quotation_id:
                teams = wizard.quotation_id.purchase_observation_recommendation_ids.mapped(
                    'team')
                is_admin = wizard.quotation_id.request_quotation_id.category == 'admin'
                labels = {
                    'applicant': 'Lid. de Proyecto',
                    'final_recommendation': 'Responsable' if is_admin else 'Compras',
                    'purchase_committee': 'Comite de Compras',
                }
                wizard.available_teams = ', '.join(
                    labels.get(team, team) for team in teams)
            else:
                wizard.available_teams = ''

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        defaults['team'] = False
        return defaults

    def action_show_team_observations(self):
        """Actualiza las observaciones según el equipo seleccionado"""
        team = self.env.context.get('team')
        self.team = team or False
        self.observation_line_ids = [(5, 0, 0)]
        if team and self.quotation_id:
            team_observations = self.quotation_id.purchase_observation_recommendation_ids.filtered(
                lambda obs: obs.team == team
            )
            self.observation_line_ids = [
                (0, 0, {'team': obs.team, 'observation': obs.observation})
                for obs in team_observations
            ]

        return self._reload_wizard()

    def _reload_wizard(self):
        """Recarga el wizard con los valores actuales"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.management.view.observations.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
