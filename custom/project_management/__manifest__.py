# -*- coding: utf-8 -*-
{
    'name': "Proyectos (TSG)",

    'summary': "Creación y gestión de proyectos",

    'description': """

        Este módulo permite la creación y gestión de proyectos dentro de la empresa.
        Facilita el control financiero, la asignación de costos y el seguimiento de unidades operativas dentro de la empresa.  

        **Características principales:**  
        - Creación y gestión de Centros de Costos.  
        - Asociación de Centros de Costos con contactos personalizados.  
        - Control y seguimiento de gastos e ingresos asociados.  
        - Integración con otros módulos empresariales según necesidades. 
        
        """,


    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'contacts_management', 'accounting', 'mail', 'utils'],

    # always loaded
    'data': [

        'security/security.xml',
        'security/actions.xml',
        'security/ir.model.access.csv',

        'views/project.xml',
        'views/cost_center.xml',
        'views/team.xml',
        'views/category.xml',

        'data/ir_cron.xml',

        'mail/end_date.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            # 'project_management/static/src/js/**/*.js',
            'project_management/static/src/scss/**/*.scss',
            # 'project_management/static/src/xml/**/*.xml',
        ],
    },
}
