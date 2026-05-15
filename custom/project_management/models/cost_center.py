
from odoo import models, fields, api, _
from unidecode import unidecode
from odoo.exceptions import ValidationError, RedirectWarning, UserError


class InheritedProjectCostCenter(models.Model):
    _inherit = 'cost.center'

    """MANY2ONE"""
    project_id = fields.Many2one(
        'project.management', string='Proyecto', required=True, ondelete='cascade', index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            analytical_account = vals.get('analytical_account_id')
            project_id = vals.get('project_id')
            code = vals.get('code')
            # Initialize to empty recordsets to avoid UnboundLocalError
            coincidences = self.env['cost.center'].browse([])
            code_coincidences = self.env['cost.center'].browse([])
            # Validar que no exista el mismo centro de costo en el mismo proyecto
            if analytical_account and project_id:
                coincidences = self.env['cost.center'].search([
                    ('analytical_account_id', '=', analytical_account),
                    ('project_id', '=', project_id)
                ])
                if coincidences:
                    raise ValidationError(
                        'Ya existe un centro de costo con la misma cuenta analítica en este proyecto, por favor verifique e intente de nuevo.'
                    )
            # Validar que el código no se repita en ningún proyecto
            if code:
                code_coincidences = self.env['cost.center'].search([
                    ('code', '=', code)
                ])
                if code_coincidences:
                    raise ValidationError(
                        'El código ya existe en otro proyecto o está duplicado, por favor verifique e intente de nuevo.'
                    )
        return super(InheritedProjectCostCenter, self).create(vals_list)

    def write(self, vals):
        # Initialize to empty recordsets to avoid UnboundLocalError
        coincidences = self.env['cost.center'].browse([])
        code_coincidences = self.env['cost.center'].browse([])
        analytical_account = vals.get(
            'analytical_account_id', self.analytical_account_id.id)
        project_id = vals.get('project_id', self.project_id.id)
        code = vals.get('code', self.code)
        # Validar que no exista el mismo centro de costo en el mismo proyecto
        if analytical_account and project_id:
            coincidences = self.env['cost.center'].search([
                ('analytical_account_id', '=', analytical_account),
                ('project_id', '=', project_id),
                ('id', '!=', self.id)
            ])
            if coincidences:
                raise ValidationError(
                    'Ya existe un centro de costo con la misma cuenta analítica en este proyecto, por favor verifique e intente de nuevo.'
                )
        # Validar que el código no se repita en ningún proyecto
        if code:
            code_coincidences = self.env['cost.center'].search([
                ('code', '=', code),
                ('id', '!=', self.id)
            ])
            if code_coincidences:
                raise ValidationError(
                    'El código ya existe en otro proyecto o está duplicado, por favor verifique e intente de nuevo.'
                )
        return super(InheritedProjectCostCenter, self).write(vals)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|',
                      ('project_id.name', operator, name),
                      ('name', operator, name),
                      ('code', operator, name)]
        return super(InheritedProjectCostCenter, self).name_search(
            name, args + domain, operator, limit)
