# -*- coding: utf-8 -*-
{
    'name': "Recursos Humanos (TSG)",

    'summary': "Módulo de Recursos Humanos para TSG",

    'description': """
Long description of module's purpose
    """,

    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",
    'icon_image': '/addons/hr/static/description/icon.png',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.1',
    'pre_init_hook': 'pre_init_hook',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr', 'contacts_management', 'utils', 'project_management', 'website'],

    # always loaded
    'data': [

        'security/security.xml',
        'security/ir.model.access.csv',

        'views/hr.xml',
        'views/eps.xml',
        'views/templates.xml',
        'views/enterprise.xml',
        'views/experience.xml',
        'views/certification.xml',
        'views/departament.xml',
        'views/arl.xml',
        'views/pension.xml',
        'views/compensation_fund.xml',
        'views/severance_fund.xml',

        'security/actions.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'rrhh/static/src/scss/rrhh.scss',
            'rrhh/static/src/js/dashboard.js',
            'rrhh/static/src/xml/dashboard.xml',
            'rrhh/static/src/scss/dashboard.scss',
            'rrhh/static/src/js/experience_one2many.js',
            'rrhh/static/src/xml/experience_one2many.xml',
            'rrhh/static/src/scss/experience_one2many.scss',
            'rrhh/static/src/js/certification_one2many.js',
            'rrhh/static/src/xml/certification_one2many.xml',
            'rrhh/static/src/scss/certification_one2many.scss',
        ],

    },
}
