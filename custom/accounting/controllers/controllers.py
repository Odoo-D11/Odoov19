# -*- coding: utf-8 -*-
# from odoo import http


# class AccountManagement(http.Controller):
#     @http.route('/account_management/account_management', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/account_management/account_management/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('account_management.listing', {
#             'root': '/account_management/account_management',
#             'objects': http.request.env['account_management.account_management'].search([]),
#         })

#     @http.route('/account_management/account_management/objects/<model("account_management.account_management"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('account_management.object', {
#             'object': obj
#         })

