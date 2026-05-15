# -*- coding: utf-8 -*-
{
    'name': "CRM (TSG)",

    'summary': "Módulo de CRM personalizado para TSG con funcionalidades específicas.",

    'description': """
        Este módulo ha sido desarrollado desde cero para cubrir las necesidades específicas de TSG. 
        Funcionalidades principales:
        - Gestión personalizada de clientes potenciales.
        - Flujo de trabajo configurable para ventas.
        - Integración básica con otros módulos específicos de TSG.
        - Interfaz amigable y reportes personalizados.
    """,

    'author': "Tsg The It Experts Sas",
    'website': "https://www.tsg.net.co/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'rrhh', 'contacts_management', 'utils'],
    'external_dependencies': {
        'python': ['validators', 'xlsxwriter'],
    },

    # always loaded
    'data': [

        'security/security.xml',

        'views/team.xml',
        'views/member.xml',
        'views/type_document.xml',
        'views/team_assignment.xml',
        'views/financial_assessment.xml',
        'views/activity.xml',
        'views/type_activity.xml',
        'views/associative_figure.xml',
        'views/category.xml',
        'views/business_line.xml',
        'views/document.xml',
        'views/type_opportunity.xml',
        'views/enterprise.xml',
        'views/source.xml',
        'views/timesheet.xml',
        'views/opportunity.xml',   

        'security/ir.model.access.csv',
        'security/actions.xml',
        'security/rules.xml',  

        'data/data.xml',

        'mail/new_opportunity.xml',
        'mail/assign_pre_sale.xml',
        'mail/opportunity_return.xml',
        'mail/upload_mvf.xml',

        'wizard/upload_document.xml',
        'wizard/crm_return.xml',
        'wizard/cancel.xml',
        'wizard/upload_financial_assessment.xml',
        'wizard/approve_financial_assessment.xml',
        'wizard/assign_pre_sale.xml',
        'wizard/upload_offer.xml',
        'wizard/present.xml',
        'wizard/won.xml',
        'wizard/pipeline.xml',
        'wizard/pre_sale_required.xml',
        
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'opportunities/static/src/js/**/*.js',
            'opportunities/static/src/scss/**/*.scss',
            'opportunities/static/src/xml/**/*.xml',
        ],
    },
}
