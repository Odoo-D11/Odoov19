from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class OpportunityTeamAssignmentLine(models.Model):
    _name = 'opportunity.team.assignment.line'
    _description = 'Línea de asignación'
    _order = 'sequence asc'
    _rec_name = 'team_id'

    """MANY2ONE"""
    assignment_id = fields.Many2one(
        'opportunity.team.assignment', string='Asignación', readonly=True, ondelete='cascade', )
    team_id = fields.Many2one('opportunity.team', string='Equipo', required=True,
                              domain="[('name', 'in', ['Preventa', 'Comercial', 'Licitaciones'])]")
    member_id = fields.Many2one(
        'opportunity.team.member', string='Responsable', required=True)
    percentage_id = fields.Many2one(
        'opportunity.percentage', string='Participación', required=True)
    role_id = fields.Many2one('opportunity.role', string='Rol', required=True)
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia')

    @api.constrains('assignment_id', 'team_id')
    def _check_unique_team(self):
        for line in self:
            if line.assignment_id:
                duplicate_lines = self.search([
                    ('assignment_id', '=', line.assignment_id.id),
                    ('team_id', '=', line.team_id.id),
                    ('id', '!=', line.id),
                    ('member_id', '=', line.member_id.id)
                ])
                if duplicate_lines:
                    raise ValidationError(
                        "El usuario '%s' ya está asignado al equipo '%s' en la oportunidad '%s'. "
                        "No se permite duplicar la asignación del mismo equipo para un mismo usuario. "
                        "Por favor, revise y ajuste los datos según corresponda."
                        % (
                            line.assignment_id.member_id.employee_id.name,
                            line.team_id.name,
                            line.assignment_id.lead_id.name if line.assignment_id.lead_id else "Sin Oportunidad"
                        )
                    )

    @api.constrains('assignment_id', 'team_id', 'percentage_id')
    def _check_team_percentage_sum(self):
        """
        Valida que para cada oportunidad, la suma de las participaciones asignadas a los equipos
        'Comercial' y 'Licitaciones' no supere el 100% en conjunto. Los demás equipos se validan
        de forma individual. El campo 'percentage' del modelo 'opportunity.percentage' es una cadena 
        con formato "50%", "100%", etc. Se extrae solo el valor numérico y se muestra sin decimales.
        """
        for line in self:
            if line.assignment_id and line.assignment_id.lead_id:
                lead = line.assignment_id.lead_id
                if line.team_id.name in ['Comercial', 'Licitaciones']:
                    # Agrupar Comercial y Licitaciones
                    lines = self.search([
                        ('assignment_id.lead_id', '=', lead.id),
                        ('team_id.name', 'in', ['Comercial', 'Licitaciones'])
                    ])
                else:
                    # Validar equipos individuales
                    lines = self.search([
                        ('assignment_id.lead_id', '=', lead.id),
                        ('team_id', '=', line.team_id.id)
                    ])
                total_percentage = sum(
                    float(l.percentage_id.percentage.replace("%", "").strip())
                    for l in lines if l.percentage_id.percentage.replace("%", "").strip().isdigit()
                )
                if total_percentage > 100:
                    raise ValidationError(
                        "La suma de las participaciones asignadas para el equipo '%s' en la oportunidad '%s' es de %d%%, "
                        "lo que supera el 100%% permitido. Por favor, revise y ajuste los valores."
                        % (line.team_id.name, lead.name, int(total_percentage))
                    )


class OpportunityTeamAssignment(models.Model):
    _name = 'opportunity.team.assignment'
    _description = 'Asignación de equipo'
    _order = 'member_id asc'
    _rec_name = 'member_id'

    """ONE2MANY"""
    team_assignment_ids = fields.One2many(
        'opportunity.team.assignment.line', 'assignment_id', string='Líneas de asignación')
    """MANY2ONE"""
    lead_id = fields.Many2one(
        'opportunity', string='Oportunidad', readonly=True, ondelete='cascade', )
    member_id = fields.Many2one(
        'opportunity.team.member', string='Responsable', required=True,
        domain="[('team_id.name', 'in', ['Preventa', 'Comercial', 'Licitaciones'])]")
    """HTML"""
    description = fields.Html(
        string='Resumen', compute='_compute_description',)
    """SELECTION"""
    rta = fields.Selection(
        [('yes', 'Sí'), ('no', 'No')], string='Respuesta', default='no')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'team_assignment_ids' not in vals or not vals['team_assignment_ids']:
                if not self.env.context.get('skip_check'):
                    name = self.env['opportunity.team.member'].browse(
                        vals.get('member_id')).employee_id.name
                    raise ValidationError(
                        _("No se pudo guardar el registro.\n\n"
                          "El usuario '%s' no tiene asignado ningún equipo. "
                          "Por favor, revise y ajuste los datos según corresponda.") % name
                    )
            if vals.get('rta') == 'yes' and vals.get('lead_id'):
                exists = self.search([
                    ('lead_id', '=', vals['lead_id']),
                    ('rta', '=', 'yes'),
                ], limit=1)
                if exists:
                    raise ValidationError(
                        _("Ya existe un responsable principal"
                          "para este mismo lead. Solo se permite uno por oportunidad.")
                    )

        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'rta' in vals or 'lead_id' in vals:
            for rec in self:
                new_lead = vals.get('lead_id') or rec.lead_id.id
                new_rta = vals.get('rta') or rec.rta
                if new_rta == 'yes':
                    conflict = self.search([
                        ('lead_id', '=', new_lead),
                        ('rta', '=', 'yes'),
                        ('id', '!=', rec.id),
                    ], limit=1)
                    if conflict:
                        raise ValidationError(
                            _("Ya existe un responsable principal"
                              "para este mismo lead. Solo se permite uno por oportunidad.")
                        )
        if 'member_id' in vals:
            for record in self:
                record.team_assignment_ids.write(
                    {'member_id': record.member_id.id})

        return res

    @api.depends('team_assignment_ids', 'member_id', 'rta')
    def _compute_description(self):
        star_icon = (
            "<span class='fa fa-star me-1' "
            "style='color: #FFC107;' "
            "title='Responsable del lead'></span>"
        )
        for rec in self:
            lines = rec.team_assignment_ids
            # Construyo el nombre, con o sin estrella
            base_name = (
                rec.member_id.employee_id.name
                if rec.member_id and rec.member_id.employee_id
                else "Sin Nombre"
            )
            name_html = (
                f"{star_icon}{base_name}"
                if rec.rta == 'yes'
                else base_name
            )

            separator = "<span class='ms-1 me-1 oe_grey'> | </span>"
            if lines:
                blocks = [
                    (
                        f"<span>{line.team_id.name or 'Equipo desconocido'}</span> "
                        f"<span>( {line.role_id.name or 'Sin rol'}, "
                        f"{line.percentage_id.percentage or '0%'} )</span>"
                    )
                    for line in lines
                ]
                rec.description = (
                    f"<span>{name_html}{separator}"
                    f"{' - '.join(blocks)}</span>"
                )
            else:
                rec.description = (
                    "<span style='color: #17a2b8;'>"
                    "<i class='fa fa-save'></i> Guarde los cambios para visualizar al nuevo integrante."
                    "</span>"
                )
