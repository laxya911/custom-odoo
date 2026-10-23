{
    'name': 'Odoo Debranding Website',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Removes Odoo branding from website footer',
    'depends': ['odoo_debranding', 'website'],
    'data': [
        'views/website_templates.xml',
    ],
    'auto_install': True,
    'installable': True,
    'license': 'LGPL-3',
}
