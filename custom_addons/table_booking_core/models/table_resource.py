# -*- coding: utf-8 -*-
from odoo import models, fields

class TableResource(models.Model):
    _name = 'table.resource'
    _description = 'Physical Table Resource for Booking'

    name = fields.Char(string='Table Name', required=True)
    capacity = fields.Integer(string='Capacity', default=2)
    is_combinable = fields.Boolean(string='Is Combinable', default=False)
    pos_table_id = fields.Many2one('restaurant.table', string='POS Table ID')
    active = fields.Boolean(string='Active', default=True)
