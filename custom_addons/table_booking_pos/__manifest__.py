{
    'name': 'Table Booking POS Integration',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Live Table Booking sync and notifications for POS',
    'description': """
        The complete Restaurant Table Booking Suite. 
        Provides live syncing of online table bookings directly to your Odoo POS.
        Includes table management, collision-proof slots, and visual floor plan alerts.
    """,
    'author': 'Geotek',
    'depends': ['pos_restaurant', 'table_booking_core', 'pos_remote_print'],
    'data': [
        'views/pos_config_views.xml',
        'views/pos_table_views.xml',
    ],
    'assets': {
        'point_of_sale.assets_prod': [
            'table_booking_pos/static/src/js/booking_notifications.js',
            'table_booking_pos/static/src/js/floor_plan_extension.js',
            'table_booking_pos/static/src/js/booking_actions.js',
            'table_booking_pos/static/src/js/booking_ui.js',
            'table_booking_pos/static/src/js/BookingCreationPopup.js',
            'table_booking_pos/static/src/xml/FloorScreen.xml',
            'table_booking_pos/static/src/xml/Navbar.xml',
            'table_booking_pos/static/src/xml/BookingsScreen.xml',
            'table_booking_pos/static/src/xml/BookingCreationPopup.xml',
            'table_booking_pos/static/src/css/pos_booking.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
    'price': 49.00,
    'currency': 'USD',
}
