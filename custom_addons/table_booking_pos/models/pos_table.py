from odoo import models, fields

class PosTable(models.Model):
    _inherit = 'restaurant.table'

    table_resource_id = fields.Many2one(
        'table.resource',
        string='Linked Booking Resource',
        help="Link this POS table to a physical booking resource for status synchronization."
    )
