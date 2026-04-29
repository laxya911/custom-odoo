{
    'name': 'Odoo Debranding',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Removes Odoo branding from emails and reports',
    'description': """
        This module removes 'Powered by Odoo' branding from standard emails and reports.
        It dynamically displays the company's report footer instead of the Odoo branding in emails.
    """,
    'depends': ['web', 'mail'],
    'data': [
        'views/web_templates.xml',
        'views/mail_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
