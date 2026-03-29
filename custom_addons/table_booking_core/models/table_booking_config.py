# -*- coding: utf-8 -*-
from odoo import models, fields, api

class TableBookingPeriod(models.Model):
    _name = 'table.booking.period'
    _description = 'Table Booking Service Period'
    _order = 'opening_time asc'

    name = fields.Char(string='Period Name', required=True, placeholder='e.g. Lunch')
    opening_time = fields.Float(string='Opening Time', default=11.0, required=True)
    closing_time = fields.Float(string='Closing Time', default=14.5, required=True)
    config_id = fields.Many2one('table.booking.config', string='Configuration', ondelete='cascade')

class TableBookingConfig(models.Model):
    _name = 'table.booking.config'
    _description = 'Table Booking Configuration'

    name = fields.Char(string='Config Name', required=True, default='Default Table Booking')
    active_booking = fields.Boolean(string='Active Booking', default=True)
    pos_config_id = fields.Many2one('pos.config', string='POS Config')
    
    # Service Periods (Split Shifts)
    service_period_ids = fields.One2many('table.booking.period', 'config_id', string='Service Periods')
    
    slot_duration_minutes = fields.Integer(string='Slot Duration (Minutes)', default=90)
    slot_interval_minutes = fields.Integer(string='Slot Interval (Minutes)', default=30)
    
    # Legacy / Default fallback
    opening_time = fields.Float(string='Default Opening Time', default=11.0)
    closing_time = fields.Float(string='Default Closing Time', default=22.0)
    
    cancel_hours_before = fields.Integer(string='Cancel Hours Before', default=24)
    allow_self_cancel = fields.Boolean(string='Allow Self-Cancellation', default=True)
    require_prepayment = fields.Boolean(string='Require Prepayment', default=False)
    deposit_percentage = fields.Float(string='Deposit Percentage', default=0.0)
    allow_table_combine = fields.Boolean(string='Allow Table Combining', default=False)
    max_party_size = fields.Integer(string='Max Party Size', default=10)

    @api.model
    def get_booking_config(self, pos_config_id=None):
        """Fetch current booking configuration for Next.js UI"""
        domain = [('active_booking', '=', True)]
        if pos_config_id:
            domain = domain + [('pos_config_id', '=', int(pos_config_id))]
            
        config = self.sudo().search(domain, limit=1)
        if not config:
            return {'status': 'error', 'message': 'Booking currently disabled'}
            
        return {
            'status': 'success',
            'config': {
                'id': config.id,
                'slot_duration': config.slot_duration_minutes,
                'slot_interval': config.slot_interval_minutes,
                'require_prepayment': config.require_prepayment,
                'deposit_percentage': config.deposit_percentage,
                'max_party_size': config.max_party_size,
                'cancel_hours_before': config.cancel_hours_before,
                'periods': [{
                    'name': p.name,
                    'open': p.opening_time,
                    'close': p.closing_time
                } for p in config.service_period_ids] or [{
                    'name': 'Full Day',
                    'open': config.opening_time,
                    'close': config.closing_time
                }]
            }
        }
