
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class InheritHrDepartament(models.Model):
    _inherit = 'hr.department'


    @api.model
    def init(self):
        super(InheritHrDepartament, self).init()
        existing_names = self.search([]).mapped("name")
        required_names = [
            "Asistencia administrativa",
            "Control Financiero",
            "Tesorería",
            "Contabilidad",
            "Talento Humano",
            "SG-SST",
            "SGA",
            "Operaciones",
            "Logística y bodega",
            "Abastecimiento",
            "Compras",
            "Comercial privado",
            "Comercial publico",
            "Licitaciones",
            "Preventa",
            "Mercadeo",
            "Juridica",
            "Gestión de la alta dirección",
            "SGC",
            "Gestión contractual",
            "Comercial",
            "Infraestructura",
            "Investigación y Desarrollo Odoo",
            "Investigación y Desarrollo Cygnus",
            "Experiencia de cliente",
            "SAGRILAF",
            "Nómina"
        ]
        missing_names = [
            name for name in required_names if name not in existing_names
        ]
        if missing_names:
            for name in missing_names:
                self.create({"name": name})



    
    