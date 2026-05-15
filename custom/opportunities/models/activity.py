
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date
import string


class TypeActivity(models.Model):
    _name = 'opportunity.type.activity'
    _description = 'Tipo de actividad'
    _order = 'name desc'
    _rec_name = 'name'

    """ONE2MANY"""
    activities_ids = fields.One2many('opportunity.activity', 'type_activity_id',
                                     string='Actividad')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Obtener los nombres existentes en el modelo
        existing_names = self.search([]).mapped("name")

        # Crear los nombres que faltan
        required_names = ["Cotizaciones", "Reunion", "Validacion tecnica",
                          "Observaciones", "Negociacion", "Subsanaciones", "Llamada"]
        missing_names = [
            name for name in required_names if name not in existing_names]

        if missing_names:
            # Crear registros para los nombres faltantes
            for name in missing_names:
                self.create({"name": name})


class Activity(models.Model):
    _name = 'opportunity.activity'
    _description = 'Actividad'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'member_id asc'
    _rec_name = 'member_id'

    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad',
        domain="[('stage', 'not in', ['won', 'lost', 'cancelled'])]")
    member_id = fields.Many2one(
        'opportunity.team.member', string='Responsable', required=True, domain="[('team_id.name', 'in', ['Comercial', 'Preventa', 'Licitaciones'])]")
    type_activity_id = fields.Many2one(
        'opportunity.type.activity', string='Actividad', required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True)
    """DATE"""
    date = fields.Date(
        string='Fecha de actividad', default=lambda self: date.today(), required=True)
    """DATETIME"""
    engagement_date = fields.Datetime(
        string='Fecha de compromiso')
    """TEXT"""
    observations = fields.Text(string='Observaciones', required=True)
    """CHAR"""
    engagement = fields.Char(string='Compromiso')
    """BOOLEAN"""
    requires_engagement_date = fields.Boolean(
        string='¿Requiere fecha de compromiso?', default=False)
    requires_lead_id = fields.Boolean(
        string='¿Requiere oportunidad?', default=False)
    requires_activity = fields.Boolean(
        string='¿Requiere actividad?', default=True)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(Activity, self).create(vals_list)
        for record in res:
            record.observations = record.observations[:1].upper(
            ) + record.observations[1:].lower()
            if record.engagement:
                record.engagement = record.engagement[:1].upper(
                ) + record.engagement[1:].lower()
        return res

    def write(self, vals):
        if 'observations' in vals:
            vals['observations'] = vals['observations'][:1].upper() + \
                vals['observations'][1:].lower()
        if 'engagement' in vals:
            vals['engagement'] = vals['engagement'][:1].upper() + \
                vals['engagement'][1:].lower()
        return super(Activity, self).write(vals)

    @api.constrains('lead_id')
    def _check_lead_id(self):
        for record in self:
            if record.lead_id.stage in ['won', 'lost', 'cancelled']:
                raise ValidationError(
                    "No se pudo guardar el registro.\n\n"
                    "La oportunidad '%s' se encuentra en estado '%s', "
                    "por lo que no se pueden agregar actividades a la misma."
                    % (record.lead_id.name, record.lead_id.stage)
                )

    @api.constrains('engagement_date')
    def _check_engagement_date(self):
        for record in self:
            if record.engagement_date and record.engagement_date.date() < record.date:
                raise ValidationError(
                    "No se pudo guardar el registro.\n\n"
                    "La fecha de compromiso no puede ser menor a la fecha de actividad."
                )

    """CREAR PIPELINE"""

    def action_create_pipeline(self):
        self.ensure_one()
        self.requires_lead_id = True
        return {
            'name': _('Pipeline'),
            'type': 'ir.actions.act_window',
            'res_model': 'opportunity',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_partner_id': self.partner_id.parent_id.id if self.partner_id.parent_id else self.partner_id.id,
                         'default_activities_ids': [(4, self.id)],
                         'default_stage': 'open',
                         'default_type': 'pipeline',
                         'default_type_opportunity_id': self.env['opportunity.type'].search([('name', '=', 'Pipeline')], limit=1).id,
                        }
        }
