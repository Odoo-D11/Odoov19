# -*- coding: utf-8 -*-
# from odoo import http


# class Expense(http.Controller):
#     @http.route('/expense/expense', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/expense/expense/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('expense.listing', {
#             'root': '/expense/expense',
#             'objects': http.request.env['expense.expense'].search([]),
#         })

#     @http.route('/expense/expense/objects/<model("expense.expense"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('expense.object', {
#             'object': obj
#         })

