
from odoo import models, fields, api


class FinancialCost(models.Model):
    _name = 'financial.cost'
    _description = 'Costos Financieros'
    _order = 'sequence, id'
    _rec_name = 'name'

    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    """FLOAT"""
    percentage = fields.Float(string='Porcentaje', readonly=True)
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', default=10)

    @api.model
    def init(self):
        """Crea automáticamente los costos financieros predeterminados si no existen"""
        default_costs = {
            'Utilidad Bruta': 0,
            'Seguro y pólizas': 0.75,
            'Overhead': 2,
            'Imprevistos': 3,
            'Comisión': 1.5,
            'Costos y gastos (Inicio del proyecto)': 0,
            'Jurídico': 0.30,
            'EBITDA': 0,
            'EBIT': 0,
            'FINANCIACION': 1.08,
            'IMPUESTOS': 0,
            'ICA': 0.97,
            'Estampillas': 1,
            '4 x Mil': 0.40,
            'Renta': 35,
            'Utilidad Neta': 0,
        }

        existing_names = self.search([]).mapped('name')
        missing_costs = {name: value for name,
                         value in default_costs.items() if name not in existing_names}

        for name, percentage in missing_costs.items():
            self.create({'name': name, 'percentage': percentage})


class CostStructure(models.Model):
    _name = 'cost.structure'
    _description = 'Estructura de Costos'
    _order = 'sequence, id'

    """MANY2MANY"""
    financial_costs_ids = fields.Many2many(
        'financial.cost', 'cost_structure_financial_cost_rel',
        'cost_structure_id', 'financial_cost_id',
        string='Costos Financieros',
        help="Lista de costos financieros asociados con la estructura."
    )
    """CHAR"""
    name = fields.Char(string='Nombre', required=True)
    """INTEGER"""
    sequence = fields.Integer(string='Secuencia', default=10)

    @api.model
    def init(self):
        """Crea una estructura de costos predeterminada si no existe"""
        if not self.search([('name', '=', 'Predeterminado')]):
            structure = self.create({'name': 'Predeterminado'})
            financial_costs = self.env['financial.cost'].search([])
            structure.financial_costs_ids = [(6, 0, financial_costs.ids)]
