# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import content_disposition, request
from odoo.tools import html_escape


class XLSXReportController(http.Controller):
    @http.route('/xlsx_reports', type='http', auth='user', methods=['POST'], csrf=False)
    def get_report_xlsx(self, model, options, output_format, report_name, token=None):
        """Recibe la petición JS y devuelve el XLSX generado."""
        uid = request.session.uid
        report_obj = request.env[model].with_user(uid)
        opts = json.loads(options)
        if output_format == 'xlsx':
            response = request.make_response(
                None,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', content_disposition(f"{report_name}.xlsx")),
                ]
            )
            report_obj.get_xlsx_report(opts, response)
            if token:
                response.set_cookie('fileToken', token)
            return response
        # En caso de error, devolvemos JSON escaped
        error = {'code': 200, 'message': 'Odoo Server Error'}
        return request.make_response(html_escape(json.dumps(error)))
