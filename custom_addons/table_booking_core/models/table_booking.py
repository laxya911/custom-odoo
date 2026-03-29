# -*- coding: utf-8 -*-
import uuid
import logging
import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class TableBooking(models.Model):
    _name = 'table.booking'
    _description = 'Table Booking Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time asc'

    name = fields.Char(string='Booking Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    config_id = fields.Many2one('table.booking.config', string='Configuration', required=True)
    resource_ids = fields.Many2many('table.resource', string='Reserved Tables')
    customer_id = fields.Many2one('res.partner', string='Customer')
    customer_name = fields.Char(string='Customer Name', required=True)
    customer_phone = fields.Char(string='Customer Phone', required=True)
    customer_email = fields.Char(string='Customer Email')
    party_size = fields.Integer(string='Party Size', required=True, default=1)
    
    start_time = fields.Datetime(string='Start Time', required=True, tracking=True)
    end_time = fields.Datetime(string='End Time', required=True, tracking=True)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ], string='Status', default='draft', tracking=True)
    
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded')
    ], string='Payment State', default='not_paid', tracking=True)
    
    cancel_token = fields.Char(string='Cancellation Token', copy=False, default=lambda self: str(uuid.uuid4()))
    booking_notes = fields.Text(string='Booking Notes')
    table_names = fields.Char(string='Tables', compute='_compute_table_names', store=True)

    @api.depends('resource_ids.name')
    def _compute_table_names(self):
        for record in self:
            record.table_names = ", ".join(record.resource_ids.mapped('name'))

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
            
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('table.booking') or _('New')
            
        records = super(TableBooking, self).create(vals_list)
        
        # Notify POS if confirmed
        for record in records:
            if record.status == 'confirmed':
                record._notify_pos_new_booking()
            
        return records

    def write(self, vals):
        res = super(TableBooking, self).write(vals)
        if 'status' in vals and vals['status'] == 'confirmed':
            for record in self:
                record._notify_pos_new_booking()
        return res

    def _notify_pos_new_booking(self):
        """Send notification to POS via Bus.bus"""
        for record in self:
            config = record.config_id.pos_config_id
            if not config:
                continue
                
            config._ensure_access_token()
            token = config.access_token
            
            payload = {
                'type': 'table_booking',
                'booking_id': record.id,
                'customer_name': record.customer_name,
                'party_size': record.party_size,
                'start_time': fields.Datetime.to_string(record.start_time),
                'message': f"New Booking: {record.customer_name} ({record.party_size}) @ {fields.Datetime.to_string(record.start_time)}",
                'sound': 'ding'
            }
            
            # Use native Odoo notification pattern
            try:
                config._notify('TABLE_BOOKING_NEW', payload)
                _logger.info("Sent TABLE_BOOKING_NEW notification for booking %s", record.name)
            except Exception as e:
                _logger.error("Failed to notify POS for booking %s: %s", record.name, str(e))

    @api.model
    def _get_available_slots(self, date_str, party_size, config_id):
        """
        Logic to find available slots for a given date and party size.
        date_str: 'YYYY-MM-DD'
        """
        config = self.env['table.booking.config'].browse(config_id)
        if not config.active_booking:
            return []

        from datetime import datetime
        day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Determine operating periods
        periods = []
        if config.service_period_ids:
            for p in config.service_period_ids:
                periods.append((p.opening_time, p.closing_time))
        else:
            periods.append((config.opening_time, config.closing_time))

        slot_duration = config.slot_duration_minutes
        slot_interval = config.slot_interval_minutes
        all_tables = self.env['table.resource'].search([('active', '=', True)])
        available_slots = []

        for open_float, close_float in periods:
            start_hour = int(open_float)
            start_min = int((open_float - start_hour) * 60)
            
            # Handle 24h case if close_float is 0 or 24
            end_hour = int(close_float) if close_float < 24 else 23
            end_min = int((close_float - int(close_float)) * 60) if close_float < 24 else 59
            
            opening_dt = datetime.combine(day_date, datetime.min.time().replace(hour=start_hour, minute=start_min))
            closing_dt = datetime.combine(day_date, datetime.min.time().replace(hour=end_hour, minute=end_min))
            if close_float < open_float:
                closing_dt += timedelta(days=1)
            
            current_slot_start = opening_dt
            while current_slot_start + timedelta(minutes=slot_duration) <= closing_dt:
                slot_end = current_slot_start + timedelta(minutes=slot_duration)
                
                # Find overlapping bookings
                overlapping_bookings = self.search([
                    ('status', 'in', ['confirmed', 'checked_in']),
                    ('start_time', '<', slot_end),
                    ('end_time', '>', current_slot_start)
                ])
                
                reserved_table_ids = overlapping_bookings.mapped('resource_ids').ids
                free_tables = all_tables.filtered(lambda t: t.id not in reserved_table_ids)
                
                # Best fit logic
                assigned_tables = self.env['table.resource']
                for t in free_tables.sorted('capacity'):
                    if t.capacity >= party_size:
                        assigned_tables = t
                        break
                
                if not assigned_tables and config.allow_table_combine:
                    combined_capacity = 0
                    for t in free_tables.filtered('is_combinable').sorted('capacity', reverse=True):
                        combined_capacity += t.capacity
                        assigned_tables += t
                        if combined_capacity >= party_size:
                            break
                    if combined_capacity < party_size:
                        assigned_tables = self.env['table.resource']

                if assigned_tables:
                    available_slots.append({
                        'time': current_slot_start.strftime('%H:%M'),
                        'start_time': fields.Datetime.to_string(current_slot_start),
                        'end_time': fields.Datetime.to_string(slot_end),
                        'tables': [{'id': t.id, 'name': t.name} for t in assigned_tables]
                    })
                
                current_slot_start += timedelta(minutes=slot_interval)
            
        return available_slots

    @api.model
    def get_available_slots(self, date=None, party_size=1, config_id=None):
        """API wrapper for slot generation"""
        if not date or not config_id:
            return {'status': 'error', 'message': 'Missing required parameters'}
        try:
            slots = self.sudo()._get_available_slots(date, int(party_size), int(config_id))
            return {'status': 'success', 'slots': slots}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @api.model
    def create_booking(self, **kwargs):
        """API wrapper for creating a booking"""
        customer_data = kwargs.get('customer') or {}
        slot_data = kwargs.get('slot') or {}
        config_id = kwargs.get('config_id')
        if not customer_data.get('name') or not slot_data.get('start_time') or not config_id:
            return {'status': 'error', 'message': 'Missing required booking data'}
            
        try:
            config = self.env['table.booking.config'].sudo().browse(int(config_id))
            customer_email = customer_data.get('email')
            
            # Timezone handling (Restaurant Time) - Default to Company TZ
            tz_name = config.pos_config_id.company_id.partner_id.tz or 'UTC'
            local_tz = pytz.timezone(tz_name)
            
            def to_utc(dt_str):
                local_dt = local_tz.localize(datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S'))
                return fields.Datetime.to_string(local_dt.astimezone(pytz.UTC))

            utc_start = to_utc(slot_data['start_time'])
            utc_end = to_utc(slot_data['end_time'])

            # 1. Partner Resolution
            partner = self.env['res.partner'].sudo().search([('email', '=', customer_email)], limit=1)
            if not partner:
                partner = self.env['res.partner'].sudo().create({
                    'name': customer_data['name'],
                    'phone': customer_data.get('phone'),
                    'email': customer_email,
                })
            elif not partner.phone and customer_data.get('phone'):
                partner.sudo().write({'phone': customer_data['phone']})

            # 2. Double Booking Check (Customer already has a booking at this time)
            existing = self.sudo().search([
                ('customer_id', '=', partner.id),
                ('status', 'in', ['confirmed', 'checked_in']),
                ('start_time', '=', utc_start)
            ], limit=1)
            if existing:
                return {'status': 'error', 'message': _('You already have a booking for this time.')}

            # 3. Overlap check (Table already booked)
            table_ids = [t['id'] for t in slot_data.get('tables', [])]
            if table_ids:
                overlapping = self.sudo().search([
                    ('status', 'in', ['confirmed', 'checked_in']),
                    ('start_time', '<', utc_end),
                    ('end_time', '>', utc_start),
                    ('resource_ids', 'in', table_ids)
                ])
                if overlapping:
                    return {'status': 'error', 'message': _('Selected table was just booked by someone else.')}

            vals = {
                'config_id': config.id,
                'customer_id': partner.id,
                'customer_name': customer_data['name'],
                'customer_phone': customer_data['phone'],
                'customer_email': customer_email,
                'party_size': int(kwargs.get('party_size', 1)),
                'start_time': utc_start,
                'end_time': utc_end,
                'resource_ids': [(6, 0, table_ids)],
                'status': 'confirmed',
                'payment_state': 'paid' if kwargs.get('payment_token') else 'not_paid',
                'booking_notes': customer_data.get('notes'),
            }
            booking = self.sudo().create(vals)
            return {'status': 'success', 'booking_ref': booking.name, 'cancel_token': booking.cancel_token}
        except Exception as e:
            _logger.error("Booking Creation Failed: %s", str(e))
            return {'status': 'error', 'message': str(e)}

    @api.model
    def cancel_booking(self, token=None):
        """API wrapper for cancelling a booking"""
        if not token: return {'status': 'error', 'message': 'Missing token'}
        booking = self.sudo().search([('cancel_token', '=', token)], limit=1)
        if not booking: return {'status': 'error', 'message': 'Booking not found'}
        
        # Check cancellation policy
        hours_to_start = (booking.start_time - datetime.utcnow()).total_seconds() / 3600
        if hours_to_start < booking.config_id.cancel_hours_before:
            return {'status': 'error', 'message': f'Cancellations must be made at least {booking.config_id.cancel_hours_before} hours in advance.'}
        
        booking.action_cancel()
        return {'status': 'success', 'message': 'Booking cancelled'}

    def action_check_in(self):
        self.ensure_one()
        self.status = 'checked_in'
        
    def action_no_show(self):
        self.ensure_one()
        self.status = 'no_show'
        
    def action_cancel(self):
        self.ensure_one()
        self.status = 'cancelled'

    @api.model
    def get_customer_activities(self, email=None):
        """API to fetch both bookings and POS orders for a customer email"""
        if not email:
            return {'status': 'error', 'message': 'Email is required'}
        
        partner = self.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
        booking_domain = [('customer_email', '=', email)]
        if partner:
            booking_domain = ['|'] + booking_domain + [('customer_id', '=', partner.id)]
            
        bookings = self.sudo().search(booking_domain, order='start_time asc')
        
        booking_data = []
        for b in bookings:
            booking_data.append({
                'id': b.id,
                'name': b.name,
                'status': b.status,
                'start_time': fields.Datetime.to_string(b.start_time),
                'party_size': b.party_size,
                'tables': [t.name for t in b.resource_ids],
                'cancel_token': b.cancel_token if b.status in ['draft', 'confirmed'] else False,
                'config_name': b.config_id.name,
            })
            
        order_data = []
        if partner:
            orders = self.env['pos.order'].sudo().search([
                ('partner_id', '=', partner.id)
            ], order='date_order desc', limit=20)
            
            for o in orders:
                order_data.append({
                    'id': o.id,
                    'ref': o.pos_reference or o.name,
                    'date': fields.Datetime.to_string(o.date_order),
                    'total': o.amount_total,
                    'state': o.state,
                    'delivery_status': getattr(o, 'delivery_status', 'unknown'),
                    'uuid': getattr(o, 'unique_uuid', False)
                })
                
        return {
            'status': 'success',
            'bookings': booking_data,
            'orders': order_data
        }
