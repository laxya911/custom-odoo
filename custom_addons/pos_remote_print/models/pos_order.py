from odoo import models

class PosOrder(models.Model):
    _inherit = 'pos.order'
    # claim_remote_print absorbed into pos_order_api
