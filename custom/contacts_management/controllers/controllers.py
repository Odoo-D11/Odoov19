# -*- coding: utf-8 -*-
# from odoo import http


# class ContactsManagement(http.Controller):
#     @http.route('/contact/contact', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/contact/contact/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('contact.listing', {
#             'root': '/contact/contact',
#             'objects': http.request.env['contact.contact'].search([]),
#         })

#     @http.route('/contact/contact/objects/<model("contact.contact"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('contact.object', {
#             'object': obj
#         })

