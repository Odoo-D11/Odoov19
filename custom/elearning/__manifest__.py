{
    'name': "eLearning (TSG)",

    'summary': 'Módulo de capacitación con guías paso a paso, videos y chatbot interactivo para procesos internos',

    'description': """
    Módulo de capacitación diseñado para mejorar la formación de los empleados en procesos internos. Incluye guías paso a paso, videos explicativos y un chatbot interactivo para resolver dudas en tiempo real, facilitando el aprendizaje y la adopción de nuevas prácticas dentro de la empresa.
    """,

    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",
    'icon_image': '/custom/elearning/static/description/icon.png',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

