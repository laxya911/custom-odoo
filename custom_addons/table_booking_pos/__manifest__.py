{
    'name': 'Table Booking POS Integration',
    'version': '1.0',
    'category': 'Point of Sale',
    'summary': 'Live Table Booking sync and notifications for POS',
    'author': 'Antigravity',
    'depends': ['point_of_sale', 'pos_restaurant', 'table_booking_core'],
    'data': [
        'views/pos_config_views.xml',
        'views/pos_table_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'table_booking_pos/static/src/js/booking_notifications.js',
            'table_booking_pos/static/src/js/floor_plan_extension.js',
            'table_booking_pos/static/src/js/booking_actions.js',
            'table_booking_pos/static/src/js/booking_ui.js',
            'table_booking_pos/static/src/xml/FloorScreen.xml',
            'table_booking_pos/static/src/xml/BookingsButton.xml',
            'table_booking_pos/static/src/xml/BookingsScreen.xml',
            'table_booking_pos/static/src/css/pos_booking.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
