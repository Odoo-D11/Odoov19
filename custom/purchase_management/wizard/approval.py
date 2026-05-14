from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re
from markupsafe import Markup
import json
from ..utils.utils import (
    convert_first_letter_to_uppercase, _show_error_notification
)


class ApprovalSupplierLine(models.TransientModel):
    _name = 'approval.supplier.line'
    _description = 'Línea de proveedor para aprobación'
    _transient_max_count = 100
    _transient_max_hours = 24

    _rec_name = 'supplier_name'

    """MANY2ONE"""
    approval_wizard_id = fields.Many2one(
        'approval.observation.wizard', string='Ventana de Aprobación', )
    """CHAR"""
    supplier_name = fields.Char(string='Proveedor', required=True)
    """HTML"""
    supplier_display = fields.Html(string='Proveedor personalizado', )
    """SELECTION"""
    state = fields.Selection([
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('recommended', 'Recomendado'),
        ('not_recommended', 'No Recomendado')
    ], string='Estado', readonly=True)

    def action_approve(self):
        # Determina el modo según el estado de la solicitud
        approval_mode = self.approval_wizard_id.approval_mode

        if approval_mode == 'recommend':
            self.state = 'recommended'
            label = 'Recomendado'
        else:
            self.state = 'approved'
            label = 'Aprobado'

        # Usa expresiones regulares para extraer solo el nombre limpio
        name = re.sub(r'<[^>]*>', '',
                      self.supplier_display).split(' - ')[0].strip()
        self.supplier_display = f'<span style="color:green;">{name}</span> <span style="color:green;">- ({label})</span>'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.observation.wizard',
            'res_id': self.approval_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reject(self):
        # Determina el modo según el estado de la solicitud
        approval_mode = self.approval_wizard_id.approval_mode

        if approval_mode == 'recommend':
            self.state = 'not_recommended'
            label = 'No Recomendado'
        else:
            self.state = 'rejected'
            label = 'Rechazado'

        # Usa expresiones regulares para extraer solo el nombre limpio
        name = re.sub(r'<[^>]*>', '',
                      self.supplier_display).split(' - ')[0].strip()
        self.supplier_display = f'<span style="color:red;">{name}</span> <span style="color:red;">- ({label})</span>'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.observation.wizard',
            'res_id': self.approval_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reset(self):
        self.state = False
        # Usa expresiones regulares para extraer solo el nombre limpio
        name = re.sub(r'<[^>]*>', '',
                      self.supplier_display).split(' - ')[0].strip()
        self.supplier_display = f'<span style="color:black; font-weight:normal;">{name}</span>'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.observation.wizard',
            'res_id': self.approval_wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ApprovalObservationLine(models.TransientModel):
    _name = 'approval.observation.line'
    _description = 'Línea de observación para aprobación'
    _transient_max_count = 100
    _transient_max_hours = 24

    """MANY2ONE"""
    approval_wizard_id = fields.Many2one(
        'approval.observation.wizard', string='Ventana de Aprobación', )
    """CHAR"""
    observation = fields.Char(string='Observación', required=True)

    @api.onchange('observation')
    def _onchange_observation(self):
        """Convierte la primera letra a mayúscula al cambiar el campo."""
        if self.observation:
            self.observation = convert_first_letter_to_uppercase(
                self.observation)


class ApprovalObservationWizard(models.TransientModel):
    _name = 'approval.observation.wizard'
    _description = 'Aprobación de proveedores'
    _transient_max_count = 100
    _transient_max_hours = 24

    """ONE2MANY"""
    supplier_ids = fields.One2many(
        'approval.supplier.line', 'approval_wizard_id', string='Proveedores', )
    observations_ids = fields.One2many(
        'approval.observation.line', 'approval_wizard_id', string='Observaciones', )
    """MANY2ONE"""
    request_quotation_id = fields.Many2one(
        'request.quotation', string='Solicitud de Cotización')
    selected_supplier_line_id = fields.Many2one(
        'approval.supplier.line', string='Proveedor',
        domain="[('approval_wizard_id', '=', id)]")
    """SELECTION"""
    approval_mode = fields.Selection([
        ('approve', 'Aprobar/Rechazar'),
        ('recommend', 'Recomendar/No Recomendar')
    ], string='Modo de Aprobación', readonly=True)
    """BOOLEAN"""
    show_instructions = fields.Boolean(
        string='Mostrar Instrucciones', default=True)
    add_observations = fields.Boolean(
        string='Agregar Observaciones', default=False)
    show_observation_instructions = fields.Boolean(
        string='Mostrar Instrucciones de Observación', default=True)
    approved = fields.Boolean(string='Aprobado', default=False, readonly=True)
    rejected = fields.Boolean(string='Rechazado', default=False, readonly=True)
    all_rejected = fields.Boolean(
        string='Todos Rechazados', default=False, readonly=True)
    rejected_by_project_leader = fields.Boolean(
        string='Vista cotización rechazada por Líder de Proyecto', default=False, readonly=True)
    """TEXT"""
    observations_json = fields.Text(
        string='Observaciones (JSON)', default='{}')
    reason_for_rejection_all_suppliers = fields.Text(
        string='Razón de Rechazo de Todos los Proveedores', )
    approve_project_leader_rejection = fields.Text(
        string='Razón del porque aprueba el rechazo del líder de proyecto', )

    @api.onchange('selected_supplier_line_id')
    def _onchange_selected_supplier_line_id(self):
        line = self.selected_supplier_line_id
        if line:
            if self.approval_mode == 'recommend':
                self.approved = line.state == 'recommended'
                self.rejected = line.state == 'not_recommended'
            else:
                self.approved = line.state == 'approved'
                self.rejected = line.state == 'rejected'
        else:
            self.approved = False
            self.rejected = False
        # Carga las observaciones del proveedor seleccionado
        self.observations_ids = [(5, 0, 0)]
        observations_data = json.loads(self.observations_json or '{}')
        key = line.supplier_name if line else None
        if key and key in observations_data:
            self.observations_ids = [
                (0, 0, {'observation': obs}) for obs in observations_data[key]
            ]

    def action_save_current_observations(self):
        """
        Guarda las observaciones del proveedor seleccionado en el campo JSON.
        """
        self.ensure_one()
        if not self.selected_supplier_line_id:
            return _show_error_notification(self, _('No hay proveedor seleccionado. Por favor, seleccione un proveedor antes de guardar las observaciones.'))
        current_obs = [
            convert_first_letter_to_uppercase(line.observation) for line in self.observations_ids if line.observation and line.observation.strip()]
        if not current_obs:
            return _show_error_notification(self, _('No hay observaciones para guardar. Por favor, agregue al menos una nota antes de guardar.'))
        observations_data = json.loads(self.observations_json or '{}')
        key = self.selected_supplier_line_id.supplier_name
        observations_data[key] = current_obs
        self.observations_json = json.dumps(observations_data, indent=4)
        supplier_name = key
        self.write({
            'selected_supplier_line_id': False,
            'observations_ids': [(5, 0, 0)]
        })
        # Muestra notificación y recarga el wizard
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'simple_notification',
            {
                'type': 'success',
                'title': _('Éxito'),
                'message': _('Las observaciones para %s se han guardado correctamente.') % supplier_name,
                'sticky': False,
            }
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.observation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_observation_instructions(self):
        """Vuelve a la pantalla de instrucciones de observaciones."""
        self.ensure_one()
        self.action_save_current_observations()
        self.show_observation_instructions = True
        self.selected_supplier_line_id = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.observation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back_to_suppliers(self):
        """Vuelve a la pantalla de lista de proveedores."""
        self.ensure_one()
        self.add_observations = False
        self.show_observation_instructions = True
        self.all_rejected = False
        self.selected_supplier_line_id = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.observation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_show_instructions(self):
        if self.show_instructions:
            self.show_instructions = False
            if not self.supplier_ids:
                names = self.request_quotation_id.quotation_line_ids.mapped(
                    'supplier_name') if self.request_quotation_id else []
                self.supplier_ids = [
                    (0, 0, {
                        'supplier_display': f'<span>{name}</span>',
                        'supplier_name': name,
                    }) for name in names
                ]
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'approval.observation.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            self.show_instructions = True
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'approval.observation.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

    def action_add_observations(self):
        rfq = self.request_quotation_id
        if self.add_observations:
            self.add_observations = False
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'approval.observation.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        else:
            # Verifica si hay proveedores aprobados o recomendados según el modo
            if self.approval_mode == 'recommend':
                approved_suppliers = any(
                    line.state == 'recommended' for line in self.supplier_ids)
            else:
                approved_suppliers = any(
                    line.state == 'approved' for line in self.supplier_ids)

            # Verifica que todos los proveedores tengan un estado asignado
            suppliers_without_state = self.supplier_ids.filtered(
                lambda line: not line.state)
            if suppliers_without_state:
                if self.approval_mode == 'recommend':
                    message = _(
                        'Debe asignar un estado (Recomendado/No Recomendado) a todos los proveedores antes de continuar. Por favor, verifique e intente nuevamente.')
                else:
                    message = _('Debe asignar un estado (Aprobado/Rechazado) a todos los proveedores antes de continuar. Por favor, verifique e intente nuevamente.') if rfq.state == 'pending_project_approval' else _(
                        'Debe aprobar al menos un proveedor antes de continuar. Por favor, verifique e intente nuevamente.')
                return _show_error_notification(self, message)
            # Validación específica para compras (modo recomendar)
            if self.approval_mode == 'recommend' and not approved_suppliers and rfq.category == 'project':
                return _show_error_notification(self, _('Debe recomendar al menos un proveedor antes de continuar. Por favor, verifique e intente nuevamente.'))
            # Validación específica para lider de proyecto (modo aprobar)
            if rfq.state == 'pending_purchase_approval' and self.approval_mode == 'approve' and not approved_suppliers:
                return _show_error_notification(self, _('Debe aprobar al menos un proveedor antes de continuar. Por favor, verifique e intente nuevamente.'))
            if rfq.state == 'pending_advisory_committee_approval' and self.approval_mode == 'approve' and not approved_suppliers:
                return _show_error_notification(self, _('Debe aprobar al menos un proveedor antes de continuar. Por favor, verifique e intente nuevamente.'))
            # Actualiza los estados
            self.all_rejected = not approved_suppliers
            self.add_observations = approved_suppliers
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'approval.observation.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

    def action_show_observations_form(self):
        """Oculta las instrucciones de las observaciones y muestra el formulario."""
        self.show_observation_instructions = False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'approval.observation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_confirm_rejection_project_leader(self):
        if not self.approve_project_leader_rejection or not self.approve_project_leader_rejection.strip():
            return _show_error_notification(self, _('Debe proporcionar una razón para aprobar el rechazo del líder de proyecto antes de continuar. Por favor, complete el campo y vuelva a intentarlo.'))
        msg = Markup(
            f"<span>Se aprueba el rechazo realizado por el líder de proyecto para las cotizaciones vinculadas a esta solicitud, correspondientes a los siguientes proveedores: <span style='color: #017e84;'>{', '.join(self.supplier_ids.filtered(lambda s: s.state == 'rejected').mapped('supplier_name'))}</span>. Por lo tanto, la solicitud volverá al area de compra para que realicen nuevas propuestas. Motivo indicado: <span style='color: #017e84;'>{convert_first_letter_to_uppercase(self.approve_project_leader_rejection.strip())}</span>.</span>"
        )
        self.request_quotation_id.sudo().message_post(body=msg)
        self.request_quotation_id.sudo().write({
            'rejected_by_project_leader': False,
            'state': 'in_shopping',
            'quotation_line_ids': [(4, qid) for qid in self.request_quotation_id.quotation_line_ids.filtered(lambda q: q.rejected).ids],
            'min_providers_qty': self.env['ir.config_parameter'].sudo().get_param('purchase_management.default_min_providers_qty', default=3),
        })
        template = self.env.ref(
            'purchase_management.mail_template_approve_project_leader_rejection')
        template.with_context(
            reason=self.approve_project_leader_rejection,
        ).send_mail(self.request_quotation_id.id, email_values={
            'email_to': self.request_quotation_id.responsible_purchase_id.employee_id.work_email,
            'email_cc': self.request_quotation_id.responsible_id.work_email,
        })

    def action_confirm_rejection_all_suppliers(self):
        supplier_names = ', '.join(self.supplier_ids.mapped('supplier_name'))
        min_qty = self.env['ir.config_parameter'].sudo().get_param(
            'purchase_management.default_min_providers_qty', default=3)
        template = self.env.ref(
            'purchase_management.mail_template_reject_all_quotations')
        rfq = self.request_quotation_id
        if not self.reason_for_rejection_all_suppliers or not self.reason_for_rejection_all_suppliers.strip():
            return _show_error_notification(self, _('Debe proporcionar una razón para el rechazo de todos los proveedores antes de continuar. Por favor, complete el campo y vuelva a intentarlo.'))
        rfq.sudo().write({
            'state': 'in_shopping' if (rfq.category == 'project' or rfq.responsible_purchase_id) else 'draft',
            'all_quotation_rejected': True,
            'quotation_line_ids': [(5, 0, 0)],
            'min_providers_qty': int(min_qty),
        })
        rfq.product_line_ids.filtered(
            lambda s: s.sent_to_emails).sudo().write({'sent_to_emails': False})
        msg = Markup(
            f"<span>"
            f"Se decidió rechazar todas las cotizaciones vinculadas a esta solicitud, "
            f"correspondientes a los siguientes proveedores: <span style='color: #017e84;'>{supplier_names}</span>, "
            f"la razón indicada es: <span style='color: #017e84;'>{convert_first_letter_to_uppercase(self.reason_for_rejection_all_suppliers.strip())}</span>, "
            f"por lo tanto, la solicitud será revertida al estado inicial para reiniciar el proceso desde cero y permitir el trabajo con nuevos proveedores."
            f"</span>"
        )
        rfq.sudo().message_post(body=msg)
        if rfq.category == 'project':
            template.with_context(
                reason=self.reason_for_rejection_all_suppliers,
                supplier_names=supplier_names,
            ).send_mail(rfq.id, email_values={
                'email_to': rfq.responsible_purchase_id.employee_id.work_email,
            })

    def action_finish_approval(self):
        """Finaliza el proceso, valida y guarda las observaciones en el chatter."""
        self.ensure_one()
        rfq = self.request_quotation_id
        # Verifica si hay un proveedor seleccionado con observaciones sin guardar
        if self.selected_supplier_line_id and self.observations_ids:
            current_obs = [
                line.observation for line in self.observations_ids if line.observation and line.observation.strip()]
            if current_obs:
                return _show_error_notification(self, _('Hay observaciones sin guardar para el proveedor seleccionado. Por favor, guarde las observaciones antes de finalizar el proceso.'))
        observations_data = json.loads(self.observations_json or '{}')
        suppliers_without_observations = [
            line.supplier_name for line in self.supplier_ids
            if not observations_data.get(line.supplier_name)
        ]
        if suppliers_without_observations:
            return _show_error_notification(self, _('Debe proporcionar al menos una observación para los siguientes proveedores: %s') % ', '.join(suppliers_without_observations))
        for supplier_line in self.supplier_ids:
            supplier_observations = observations_data.get(supplier_line.supplier_name, [])
            quotation = self.env['quotation.quotation'].sudo().search([
                ('request_quotation_id', '=', rfq.id),
                ('supplier_name', '=ilike', supplier_line.supplier_name.strip()),
            ], limit=1)
            team = {
                'pending_project_approval': 'applicant',
                'pending_purchase_approval': 'final_recommendation',
                'pending_advisory_committee_approval': 'purchase_committee'
            }.get(rfq.state, '') if rfq.category == 'project' else {
                'pending_advisory_committee_approval': 'purchase_committee',
            }.get(rfq.state, 'final_recommendation')
            if quotation:
                for obs_text in supplier_observations:
                    if obs_text and obs_text.strip():
                        self.env['purchase.project.observation.recommendation'].sudo().create({
                            'quotation_id': quotation.id,
                            'team': team,
                            'observation': obs_text.strip(),
                            'state': supplier_line.state,
                        })
                # Marcar cotización adjudicada cuando el comité la aprueba o recomienda
                if team == 'purchase_committee' and supplier_line.state in ('approved', 'recommended'):
                    quotation.sudo().write({'awarded': True})
        is_project_approval = rfq.state == 'pending_project_approval'
        all_rejected = (
            is_project_approval and
            all(line.state == 'rejected' for line in self.supplier_ids)
        )
        some_rejected = (
            is_project_approval and
            any(line.state == 'rejected' for line in self.supplier_ids) and
            not all_rejected
        )

        if some_rejected:
            # El Gerente orientó la selección: marca las rechazadas y avanza a Compras
            quotation_rejected = self.supplier_ids.filtered(lambda s: s.state == 'rejected')
            rejected_names = quotation_rejected.mapped('supplier_name')
            rfq.quotation_line_ids.filtered(
                lambda q: q.supplier_name.strip().lower() in [n.strip().lower() for n in rejected_names]
            ).sudo().write({'rejected': True})

        if all_rejected:
            # El Gerente rechazó todo: activa SAGRILAFT
            quotation_rejected = self.supplier_ids.filtered(lambda s: s.state == 'rejected')
            rejected_names = quotation_rejected.mapped('supplier_name')
            rfq.sudo().write({'rejected_by_project_leader': True})
            rfq.quotation_line_ids.filtered(
                lambda q: q.supplier_name.strip().lower() in [n.strip().lower() for n in rejected_names]
            ).sudo().write({'rejected': True})
            msg = Markup(
                "<span>El <span style='color: #017e84;'>Gerente de Proyecto</span> ha rechazado <b>todas</b> las cotizaciones "
                "vinculadas a esta solicitud (%s). La solicitud queda en espera de que el área responsable defina si se continúa "
                "con alguna excepción o si el <span style='color: #017e84;'>área de Compras</span> debe generar una nueva propuesta.</span>"
                % ', '.join(rejected_names)
            )
            rfq.sudo().message_post(body=msg)
            responsable_approval_user = self.env['ir.config_parameter'].sudo().get_param(
                'purchase_management.approval_min_providers_user_id', default=False)
            if responsable_approval_user:
                notify_template = self.env.ref(
                    'purchase_management.mail_template_notify_project_leader_rejection')
                notify_template.with_context(
                    supplier_names=', '.join(rejected_names),
                ).send_mail(rfq.id, email_values={
                    'email_to': self.env['res.users'].search([
                        ('id', '=', int(responsable_approval_user))], limit=1).employee_id.work_email,
                })

        project_leader_rejected = all_rejected
        if not project_leader_rejected:
            template = self.env.ref(
                'purchase_management.mail_template_approval_notification')
            if rfq.category == 'project':
                next_state = {
                    'pending_project_approval': 'pending_purchase_approval',
                    'pending_purchase_approval': 'pending_advisory_committee_approval',
                    'pending_advisory_committee_approval': 'approved'
                }.get(rfq.state)
                if next_state:
                    rejected_note = ''
                    if some_rejected:
                        rejected_note = (
                            " Ha marcado como no aprobadas las cotizaciones de: <span style='color: #017e84;'>%s</span>."
                            % ', '.join(rejected_names)
                        )
                    messages = {
                        'pending_project_approval': Markup(
                            "<span>El <span style='color: #017e84;'>Gerente de Proyecto</span> ha registrado sus observaciones sobre la solicitud de cotización.%s"
                            " Ahora corresponde al <span style='color: #017e84;'>área de Compras</span> revisar dichas observaciones, realizar su análisis y preparar la propuesta final para el comité de compras.</span>"
                            % rejected_note
                        ),
                        'pending_purchase_approval': Markup(
                            "<span>El <span style='color: #017e84;'>área de compras</span> ha registrado sus observaciones sobre la solicitud de cotización. Ahora corresponde al <span style='color: #017e84;'>comité de compras</span> revisar dichas observaciones y tomar una decisión final sobre la aprobación de las cotizaciones presentadas.</span>"
                        ),
                        'pending_advisory_committee_approval': Markup(
                            "<span>El <span style='color: #017e84;'>comité de compras</span> registró sus observaciones sobre la solicitud de cotización. Ahora corresponde al"
                            " <span style='color: #017e84;'>área de compras</span> notificar a los proveedores seleccionados sobre la aprobación de sus cotizaciones y proceder con la generación de la orden.</span>"
                        ),
                    }.get(rfq.state, '')
                    msg = messages
                    rfq.sudo().write({'state': next_state})
            elif rfq.category == 'admin':
                if self.approval_mode == 'recommend':
                    rfq.sudo().write({
                        'state': 'pending_advisory_committee_approval',
                    })
                    msg = Markup(
                        "<span>Se ha registrado la recomendación sobre las cotizaciones presentadas. Ahora corresponde al <span style='color: #017e84;'>comité de compras</span> revisar dicha recomendación y tomar una decisión final sobre la aprobación de las cotizaciones.</span>"
                    )
                else:
                    rfq.sudo().write({
                        'state': 'approved',
                    })
                    msg = Markup(
                        "<span>El <span style='color: #017e84;'>comité de compras</span> registró sus observaciones sobre la solicitud de cotización. Ahora corresponde al <span style='color: #017e84;'>responsable de la solicitud</span> notificar a los proveedores seleccionados sobre la aprobación de sus cotizaciones y proceder con la generación de la orden.</span>"
                    )
            if rfq.state == 'approved':
                template.send_mail(rfq.id, email_values={
                    'email_to': rfq.responsible_purchase_id.employee_id.work_email if (rfq.category == 'project' or rfq.responsible_purchase_id) else rfq.responsible_id.work_email,
                    'email_cc': rfq.responsible_id.work_email if (rfq.category == 'project' or rfq.responsible_purchase_id) else '',
                })
            rfq.sudo().message_post(body=msg)
