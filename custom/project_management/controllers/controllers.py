# -*- coding: utf-8 -*-
# from odoo import http


# class CostCenter(http.Controller):
#     @http.route('/cost_center/cost_center', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/cost_center/cost_center/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('cost_center.listing', {
#             'root': '/cost_center/cost_center',
#             'objects': http.request.env['cost_center.cost_center'].search([]),
#         })

#     @http.route('/cost_center/cost_center/objects/<model("cost_center.cost_center"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('cost_center.object', {
#             'object': obj
#         })

