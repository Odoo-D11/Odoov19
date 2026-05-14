# -*- coding: utf-8 -*-
{
    'name': "Contactos (TSG)",

    'summary': "Modulo personalizado para la gestion de contactos",

    'description': """
Long description of module's purpose
    """,
    'icon_image': '/contacts_management/static/description/icon.png',
    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.2',

    # any module necessary for this one to work correctly
    'depends': ['base', 'contacts', 'utils', 'privacy_lookup', 'portal'],
    'external_dependencies': {
        'python': ['unidecode', 'rapidfuzz', 'Levenshtein'],
    },
    # always loaded
    'data': [

        'security/security.xml',

        'views/identification.xml',
        'views/city.xml',
        'views/state.xml',
        'views/res_partner.xml',

        'wizard/bulk_import_contacts.xml',

       'security/ir.model.access.csv',
        'security/actions.xml',

        'data/data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'contacts_management/static/src/**/*',
        ],
    },
}
