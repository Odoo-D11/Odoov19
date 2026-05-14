# -*- coding: utf-8 -*-
# from odoo import http


# class Rrhh(http.Controller):
#     @http.route('/rrhh/rrhh', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/rrhh/rrhh/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('rrhh.listing', {
#             'root': '/rrhh/rrhh',
#             'objects': http.request.env['rrhh.rrhh'].search([]),
#         })

#     @http.route('/rrhh/rrhh/objects/<model("rrhh.rrhh"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('rrhh.object', {
#             'object': obj
#         })

