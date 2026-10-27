# -*- coding: utf-8 -*-
from odoo import models, api

class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def get_param(self, key, default=False):
        """Compatibility layer for Odoo 20: get_param was replaced by get_str/get_bool/get_int/get_float."""
        val = self.get_str(key, None)
        return val if val is not None else default

    @api.model
    def set_param(self, key, value):
        """Compatibility layer for Odoo 20: set_param was replaced by set_str/set_bool/set_int/set_float."""
        return self.set_str(key, value)
