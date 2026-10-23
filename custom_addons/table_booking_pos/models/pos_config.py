from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'

    accept_table_bookings = fields.Boolean(
        string='Accept Table Bookings',
        default=True,
        help="If enabled, this POS will receive real-time table booking notifications."
    )
