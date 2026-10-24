{
    'name': 'Odoo Debranding',
    'version': '20.0.1.0.0',
    'category': 'Hidden',
    'author': 'Custom',
    'summary': 'Removes Odoo branding from emails, reports, and digests',
    'description': """
        This module removes 'Powered by Odoo' branding from standard emails, reports, and digest emails.
        It dynamically displays the company's report footer instead of the Odoo branding in emails.
    """,
    'depends': ['web', 'mail', 'digest'],
    'data': [
        'views/web_templates.xml',
        'views/mail_templates.xml',
        'views/digest_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
