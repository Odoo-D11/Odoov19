
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class TypeOpportunity(models.Model):
    _name = 'opportunity.type'
    _description = 'Tipo de oportunidad'
    _order = 'name asc'
    _rec_name = 'name'

    """MANY2ONE"""
    sector_id = fields.Many2one(
        'opportunity.sector', string='Sector')
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)

    @api.model
    def init(self):
        # Listas de nombres requeridos
        public = ["Licitación pública", "Seleccion abreviada", "Subasta inversa",
                  "Estudio de mercado", "Contrato interadministrativo", "Régimen especial",
                  "Mínima cuantía", "Contratación directa", "Concurso de méritos"]
        private = ["RFP", "RFI"]
        other = ["Pipeline"]

        # Obtener los sectores "Público" y "Privado"
        sector_public = self.env['opportunity.sector'].search(
            [('name', '=', 'Público')], limit=1)
        sector_private = self.env['opportunity.sector'].search(
            [('name', '=', 'Privado')], limit=1)

        # Validar y/o corregir las categorías del sector público
        for name in public:
            record = self.search([('name', '=', name)], limit=1)
            if not record:
                # Crear el registro si no existe
                self.create({
                    "name": name,
                    "sector_id": sector_public.id
                })
            elif record.sector_id != sector_public:
                # Corregir el sector si es incorrecto
                record.sector_id = sector_public

        # Validar y/o corregir las categorías del sector privado
        for name in private:
            record = self.search([('name', '=', name)], limit=1)
            if not record:
                # Crear el registro si no existe
                self.create({
                    "name": name,
                    "sector_id": sector_private.id
                })
            elif record.sector_id != sector_private:
                # Corregir el sector si es incorrecto
                record.sector_id = sector_private
        
        for name in other:
            record = self.search([('name', '=', name)], limit=1)
            if not record:
                # Crear el registro si no existe
                self.create({
                    "name": name,
                    "sector_id": False
                })
            elif record.sector_id != False:
                # Corregir el sector si es incorrecto
                record.sector_id = False
