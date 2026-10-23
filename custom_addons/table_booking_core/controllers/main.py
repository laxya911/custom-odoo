# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class TableBookingController(http.Controller):

    @http.route('/api/table_booking/config', type='jsonrpc', auth='public', methods=['POST'], website=True)
    def get_booking_config(self, **kwargs):
        """Fetch current booking configuration for Next.js UI"""
        pos_config_id = kwargs.get('pos_config_id')
        domain = [('active_booking', '=', True)]
        if pos_config_id:
            domain.append(('pos_config_id', '=', int(pos_config_id)))
            
        config = request.env['table.booking.config'].sudo().search(domain, limit=1)
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
            }
        }

    @http.route('/api/table_booking/slots', type='jsonrpc', auth='public', methods=['POST'], website=True)
    def get_available_slots(self, date=None, party_size=1, config_id=None, **kwargs):
        """Get available booking slots for a date and party size"""
        if not date or not config_id:
            return {'status': 'error', 'message': 'Missing required parameters'}
            
        try:
            slots = request.env['table.booking'].sudo()._get_available_slots(date, int(party_size), int(config_id))
            return {
                'status': 'success',
                'slots': slots
            }
        except Exception as e:
            _logger.error("Error fetching slots: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/table_booking/book', type='jsonrpc', auth='public', methods=['POST'], website=True)
    def create_booking(self, **kwargs):
        """Create a new table booking"""
        customer_data = kwargs.get('customer')
        slot_data = kwargs.get('slot')
        config_id = kwargs.get('config_id')
        
        if not customer_data or not slot_data or not config_id:
            return {'status': 'error', 'message': 'Missing booking data'}
            
        try:
            # Final collision check before creation
            overlapping = request.env['table.booking'].sudo().search([
                ('status', 'in', ['confirmed', 'checked_in']),
                ('start_time', '<', slot_data['end_time']),
                ('end_time', '>', slot_data['start_time']),
                ('resource_ids', 'in', [t['id'] for t in slot_data['tables']])
            ])
            
            if overlapping:
                return {'status': 'error', 'message': 'Selected table was just booked by someone else. Please refresh.'}
                
            vals = {
                'config_id': int(config_id),
                'customer_name': customer_data['name'],
                'customer_phone': customer_data['phone'],
                'customer_email': customer_data.get('email'),
                'party_size': int(kwargs.get('party_size', 1)),
                'start_time': slot_data['start_time'],
                'end_time': slot_data['end_time'],
                'resource_ids': [(6, 0, [t['id'] for t in slot_data['tables']])],
                'status': 'confirmed', # Auto-confirm for now, or 'draft' if payment needed
                'payment_state': 'paid' if kwargs.get('payment_token') else 'not_paid',
                'booking_notes': customer_data.get('notes'),
            }
            
            # Map to partner if logged in
            if not request.env.user._is_public():
                vals['customer_id'] = request.env.user.partner_id.id
            
            booking = request.env['table.booking'].sudo().create(vals)
            
            return {
                'status': 'success',
                'booking_ref': booking.name,
                'cancel_token': booking.cancel_token
            }
        except Exception as e:
            _logger.error("Error creating booking: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/api/table_booking/cancel', type='jsonrpc', auth='public', methods=['POST'], website=True)
    def cancel_booking(self, token=None, **kwargs):
        """Self-cancel a booking via token"""
        if not token:
            return {'status': 'error', 'message': 'Missing token'}
            
        booking = request.env['table.booking'].sudo().search([('cancel_token', '=', token)], limit=1)
        if not booking:
            return {'status': 'error', 'message': 'Booking not found'}
            
        # Check cancellation policy
        from datetime import datetime
        now = datetime.now()
        hours_to_start = (booking.start_time - now).total_seconds() / 3600
        
        if hours_to_start < booking.config_id.cancel_hours_before:
            return {'status': 'error', 'message': f'Cannot cancel less than {booking.config_id.cancel_hours_before} hours before start.'}
            
        booking.action_cancel()
        return {'status': 'success', 'message': 'Booking cancelled successfully'}
