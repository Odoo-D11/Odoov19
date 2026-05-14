# -*- coding: utf-8 -*-
{
    'name': "Utils (TSG)",
    'summary': "Funciones útiles para otros módulos",
    'description': """
Este módulo proporciona un conjunto de funciones reutilizables que facilitan el desarrollo de otros módulos en Odoo. 
Su objetivo es centralizar utilidades comunes, evitando la duplicidad de código y mejorando la mantenibilidad de los proyectos.

Incluye, por ejemplo:

    - Función para convertir la primera letra de un string a mayúscula y el resto a minúscula.
    - Función para validar que un campo tipo HTML no esté vacío.
    - Función para comparar y validar coincidencia de nombres.
    - Función para validar que una URL sea válida.
    - Otras utilidades que pueden ser requeridas por diferentes módulos.

    - Oculta los modulos de Aplicaciones y Sitio web para evitar que los usuarios los vean.
    - Hereda la vista de desinstalación de módulos para personalizar el comportamiento.

Utiliza este módulo como base para importar funciones que agilicen el desarrollo y garanticen buenas prácticas en tus implementaciones.
    """,
    'icon_image': '/utils/static/description/icon.png',
    'author': "Tsg The It Experts Sas",
    'website': "https://www.yourcompany.com",
    'category': 'TSG',
    'version': '0.1',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr', 'auth_signup', 'utm', 'website'],
    'external_dependencies': {
        'python': ['unidecode', 'validators', 'beautifulsoup4'],
    },
    'data': [

        'security/security.xml',

        # 'mail/invitation.xml',

        'views/utils.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'utils/static/src/scss/*.scss',
            'utils/static/src/widget/**/*',
            'utils/static/src/js/**/*.js',
        ],
    },
}
