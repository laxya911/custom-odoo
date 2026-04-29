{
    'name': 'Odoo Debranding Digest',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Removes Odoo branding from digest emails',
    'depends': ['odoo_debranding', 'digest'],
    'data': [
        'views/digest_templates.xml',
    ],
    'auto_install': True,
    'installable': True,
    'license': 'LGPL-3',
}
