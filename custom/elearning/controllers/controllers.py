# from odoo import http


# class Elearning(http.Controller):
#     @http.route('/elearning/elearning', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/elearning/elearning/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('elearning.listing', {
#             'root': '/elearning/elearning',
#             'objects': http.request.env['elearning.elearning'].search([]),
#         })

#     @http.route('/elearning/elearning/objects/<model("elearning.elearning"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('elearning.object', {
#             'object': obj
#         })

