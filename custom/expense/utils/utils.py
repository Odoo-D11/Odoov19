from pytz import timezone
from datetime import datetime
from typing import Iterable, List, Optional
from odoo.addons.utils.models.utils import (  # type: ignore
    is_html_content_empty,
    format_html_to_sentence_case,
    convert_first_letter_to_uppercase,
    is_valid_url
)


def get_hour(expense):
    """Obtiene la hora actual en la zona horaria de Bogotá."""
    tz = timezone('America/Bogota')  # Cambia a tu zona horaria preferida
    hour = datetime.now().astimezone(tz).hour
    return hour


def _get_team_members_emails(expense, team_name: str) -> List[str]:
    """Return work emails for all members of the given team."""
    members = expense.env['expense.member'].sudo().search([
        ('team_id.name', '=', team_name),
    ])
    return [
        m.employee_id.work_email
        for m in members
        if m.employee_id.work_email
    ]


def get_accounting_team_emails(expense):
    """Obtiene la lista de correos de los integrantes del equipo de contabilidad."""
    return _get_team_members_emails(expense, 'Contabilidad')


def calculate_total_requested_amount(displacements):
    """Calcula el total solicitado a partir de las líneas de servicio."""
    return sum(
        sum(line.total_amount for line in displacement.service_line_ids)
        for displacement in displacements
    )


def get_treasury_team_emails(expense):
    """Obtiene la lista de correos de los integrantes del equipo de tesorería."""
    return _get_team_members_emails(expense, 'Tesorería')


def get_team_emails(expense):
    """Obtiene la lista de correos dependiendo del proyecto."""
    team_id = expense.env['project.management'].sudo().search(
        [('id', '=', expense.project_id.id)], limit=1).team_id.id
    members = expense.env['project.member'].sudo().search(
        [('team_id', '=', team_id)])
    emails = []
    for member in members:
        if member.employee_id.work_email:
            emails.append(member.employee_id.work_email)
    return emails


def send_expense_mail(
    expense,
    template_xmlid: str,
    to: Iterable[str],
    cc: Optional[Iterable[str]] = None,
    **context,
):
    ctx = {'hour': get_hour(expense), **context}
    email_values = {
        'email_from': 'odoo@tsg.net.co',
        'email_to': ', '.join(to),
    }
    if cc:
        email_values['email_cc'] = ', '.join(cc)

    expense.env.ref(template_xmlid).with_context(**ctx).send_mail(
        expense.id, email_values=email_values
    )


def get_expense_evidence_and_reimbursement(expense):
    """Retorna la evidencia y el reembolso más recientes para una solicitud"""
    evidence_attachments = expense.env['ir.attachment'].sudo().search([
        ('res_id', '=', expense.id),
        ('res_model', '=', 'expense.expense'),
        ('description', '=', 'Evidencia de la solicitud')
    ], order='create_date desc')
    evidence = evidence_attachments[0].datas if evidence_attachments else False

    reimbursement_attachments = expense.env['ir.attachment'].sudo().search([
        ('res_id', '=', expense.id),
        ('res_model', '=', 'expense.expense'),
        ('description', '=', 'Evidencia del reembolso')
    ], order='create_date desc')
    reimbursement = reimbursement_attachments[0].datas if reimbursement_attachments else False

    return evidence, reimbursement
