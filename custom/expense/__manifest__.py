# -*- coding: utf-8 -*-
{
    'name': "Gastos (TSG)",

    'summary': "Módulo de gestión de gastos para técnicos o empleados",

    'description': """
    Módulo que permite a los técnicos adjuntar evidencias visuales directamente en las solicitudes, restringiendo los archivos a imágenes en formato JPG, JPEG o PNG.
    – Validación de extensiones (*.pdf) y tamaño máximo configurable.  
    – Fácil de usar: solo arrastrar o seleccionar el archivo.
    """,

    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'rrhh', 'project_management', 'accounting', 'contacts_management', 'utils'],
    'external_dependencies': {
        'python': ['holidays'],
    },

    # always loaded
    'data': [

        'security/security.xml',
        'security/ir.model.access.csv',
        'security/actions.xml',

        'data/data.xml',
        'data/ir_cron.xml',

        'views/expense.xml',
        'views/displacement.xml',
        'views/type_ticket.xml',
        'views/team.xml',
        'views/enterprise.xml',
        'views/service.xml',
        'views/rejection_reason.xml',
        'views/category.xml',
        'views/personal_information.xml',
        'views/refund.xml',

        'mail/approval.xml',
        'mail/pay.xml',
        'mail/legalization.xml',

        'wizard/approve.xml',
        'wizard/attach_evidence.xml',
        'wizard/attach_reimburse.xml',
        'wizard/approve_legalization.xml',
        'wizard/pay.xml',
        'wizard/view_attachment.xml'


    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'expense/static/src/scss/**/*.scss',
            'expense/static/src/widget/**/*',
        ],
    },
}
