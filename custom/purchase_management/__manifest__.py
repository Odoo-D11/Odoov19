# -*- coding: utf-8 -*-
{
    'name': "Compras (TSG)",

    'summary': "Módulo de gestión de compras",

    'description': """
        Este módulo permite gestionar el proceso de compras 
        dentro de una empresa, facilitando la creación, seguimiento y 
        control de órdenes de compra, solicitudes de materiales y proveedores. 
        Automatiza tareas administrativas, mejora la trazabilidad y 
        optimiza la gestión de adquisiciones para asegurar el abastecimiento
        eficiente de bienes y servicios necesarios para la operación empresarial.
    """,

    'author': "Tsg The IT Experts",
    'website': "https://www.tsg.net.co/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/18.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'contacts_management', 'accounting', 'project_management', 'mail', 'rrhh', 'warehouse', 'utils'],
    'external_dependencies': {
        'python': ['markupsafe']
    },

    # always loaded
    'data': [

        'security/security.xml',

        'data/data.xml',
        'data/ir_cron.xml',

        'views/team.xml',
        'views/member.xml',
        'views/request_type.xml',
        'views/quotation.xml',
        'views/res_partner.xml',
        'views/request_quotation.xml',
        'views/purchase_order.xml',
        'views/additional_information.xml',
        'views/res_config_settings.xml',
        'views/enterprise.xml',
        'views/purchase_administrative.xml',

        'security/ir.model.access.csv',

        'mail/project_leader.xml',
        'mail/purchase.xml',
        'mail/purchase_order.xml',
        'mail/supplier.xml',
        'mail/sagrilaft.xml',
        'mail/reject.xml',
        'mail/approval.xml',
        'mail/return_to_requester.xml',

        'wizard/reject.xml',
        'wizard/cancel.xml',
        'wizard/send_mail.xml',
        'wizard/approval.xml',
        'wizard/view_observations.xml',
        'wizard/approval_sagrilaft.xml',
        'wizard/bulk_upload_products.xml',
        'wizard/bulk_upload_quotations.xml',
        'wizard/purchase_order_send_mail.xml',
        'wizard/return_to_requester.xml',

        'report/format/custom.xml',
        'report/purchase_order.xml',

        'security/actions.xml',

    ],

    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'purchase_management/static/src/scss/purchase.scss',
            'purchase_management/static/src/components/**/*',
            'purchase_management/static/src/widget/**/*',
        ],
    },
}
