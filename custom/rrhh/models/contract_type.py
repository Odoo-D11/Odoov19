
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError, AccessError

class InheritHrContractType(models.Model):
    _inherit = 'hr.contract.type'
    
    @api.model
    def init(self):
        existing_names = self.search([]).mapped("name")
        country = self.env.ref('base.co', raise_if_not_found=False)
        required_names = [
            {"name": "Indefinido", "code": "IND", "country_id": country.id if country else False},
            {"name": "Término fijo", "code": "TF", "country_id": country.id if country else False},
            {"name": "Obra o labor", "code": "OL", "country_id": country.id if country else False},
            {"name": "Aprendizaje", "code": "AP", "country_id": country.id if country else False},
        ]
        missing = [r for r in required_names if r["name"] not in existing_names]
        for vals in missing:
            self.sudo().create(vals)
