# -*- coding: utf-8 -*-
{
    'name': "Inventario (TSG)",

    'summary': "Gestión de inventario y almacenes",

    'description': """
Módulo para la gestión de inventario y control de almacenes en Odoo.
Permite llevar un registro de los productos en stock, gestionar entradas y salidas,
y realizar inventarios de manera eficiente.
    """,

    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",
    'icon_image': '/custom/warehouse/static/description/icon.png',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'TSG',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'contacts_management', 'accounting'],

    # always loaded
    'data': [

        'security/security.xml',

        'views/product.xml',
        'views/warehouse.xml',
        'views/category.xml',
        'views/picking_type.xml',
        'views/picking.xml',
        'views/quant.xml',
        'views/scrap.xml',
        'views/variant_alias.xml',
        'views/uom.xml',

        'security/ir.model.access.csv',
        'security/actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'warehouse/static/src/js/*.js',
            'warehouse/static/src/xml/*.xml',
            'warehouse/static/src/widget/**/*',
        ],
    },

    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
