{
    'name': 'Table Booking Core',
    'version': '1.0',
    'category': 'Sales/POS',
    'summary': 'Core logic for Online Table Booking System',
    'description': """
        Handles table resources, booking configurations, and collision-proof 
        slot generation for online table bookings.
    """,
    'author': 'Antigravity',
    'depends': ['point_of_sale', 'pos_order_api', 'ram_website', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/table_booking_config_views.xml',
        'views/table_resource_views.xml',
        'views/table_booking_views.xml',
        'views/menu_items.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
