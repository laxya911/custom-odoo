# -*- coding: utf-8 -*-
from odoo import models, api


class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _load_pos_data_domain(self, data):
        # Ensure company currency and POS config currency are active so POS UI never crashes with company.currency_id undefined
        config = data.get('pos.config')
        if config:
            needed = config.company_id.currency_id | config.currency_id
            inactive = needed.filtered(lambda c: not c.active)
            if inactive:
                inactive.sudo().write({'active': True})
        return super()._load_pos_data_domain(data)
