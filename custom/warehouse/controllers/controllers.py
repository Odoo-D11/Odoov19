# -*- coding: utf-8 -*-
# from odoo import http


# class Warehouse(http.Controller):
#     @http.route('/warehouse/warehouse', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/warehouse/warehouse/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('warehouse.listing', {
#             'root': '/warehouse/warehouse',
#             'objects': http.request.env['warehouse.warehouse'].search([]),
#         })

#     @http.route('/warehouse/warehouse/objects/<model("warehouse.warehouse"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('warehouse.object', {
#             'object': obj
#         })

