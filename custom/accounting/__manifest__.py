# -*- coding: utf-8 -*-
{
    'name': "Contabilidad (TSG)",

    'summary': "Módulo personalizado para la gestión de contabilidad",

    'description': """
    Long description of module's purpose
    """,

    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'contacts_management', 'utils', 'mail'],
    'external_dependencies': {
        'python': ['unidecode', 'rapidfuzz'],
    },
    # always loaded
    'data': [

        'views/analytical_account.xml',
        'views/payment_terms.xml',
        'views/res_currency.xml',
        'views/cost_center.xml',
        'data/cron.xml',

        'security/security.xml',
        'security/ir.model.access.csv',
        'security/actions.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
