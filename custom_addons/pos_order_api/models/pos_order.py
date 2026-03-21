import uuid
import logging
from pprint import pformat
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

# Default Delivery Preset ID (configured in Odoo)
# Default Delivery Preset ID (configured in Odoo)
# DELIVERY_PRESET_ID = 3  <-- REMOVED per user request for dynamic lookup

class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ID to prevent duplicates (Idempotency)
    unique_uuid = fields.Char(string='Unique API UUID', help='Unique identifier for API orders', copy=False, index=True)
    
    # Source tracking
    is_api_order = fields.Boolean(string='Is API Order', default=False, readonly=True)
    api_source = fields.Selection([
        ('native_web', 'Native Website'),
        ('uber', 'Uber Eats'),
        ('doordash', 'DoorDash'),
        ('zomato', 'Zomato'),
        ('swiggy', 'Swiggy'),
        ('other', 'Other')
    ], string='API Source', readonly=True)
    
    # Delivery Status Workflow (Restaurant-side tracking)
    # Note: For Uber Eats, driver tracking is handled by Uber's app
    delivery_status = fields.Selection([
        ('received', 'Order Received'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('on_the_way', 'On the Way'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='Delivery Status', default='received', tracking=True,
       help='Restaurant-side order status for delivery workflow')
    
    # Remote printing status
    is_remote_printed = fields.Boolean(string='Remote Printed', default=False, help="True if printed to kitchen via remote bus")
    remote_printer_lock = fields.Many2one('pos.session', string='Printer Lock', help="Session that claimed this print job")
    
    # Delivery Metadata
    api_customer_name = fields.Char(string='API Customer Name')
    api_customer_phone = fields.Char(string='API Customer Phone')
    api_delivery_address = fields.Text(string='API Delivery Address')
    api_order_notes = fields.Text(string='API Order Notes')

    _unique_uuid_uniq = models.Constraint('UNIQUE(unique_uuid)', 'Order UUID must be unique!')

    @api.model
    def create_api_order(self, order_data):
        """
        Create POS order directly using DB-first approach.
        Calculates totals manually to avoid compute errors.
        """
        _logger.info(f"CREATE_API_ORDER: Start. Simulate: {order_data.get('simulate')}")
        # 1. Idempotency check
        unique_uuid = order_data.get('uuid')
        existing = self.search([('unique_uuid', '=', unique_uuid)], limit=1)
        if existing:
            _logger.info(f"Duplicate Order Ignored: {unique_uuid}")
            return existing

        # 2. Session resolution
        # STRICT MODE: Only find session that is OPEN, Delivery is ACTIVE, and Remote Orders ACCEPTED.
        # We do NOT fallback to just any open session.
        session_id = order_data.get('session_id')
        if not session_id:
            session = self.env['pos.session'].search([
                ('state', '=', 'opened'),
                ('delivery_active', '=', True),
                ('config_id.accept_remote_orders', '=', True)
            ], limit=1)
            
            if not session:
                 raise UserError(_("Order Rejected: No active POS session found accepting remote orders."))
        else:
            session = self.env['pos.session'].browse(session_id)
            if not session.exists() or session.state != 'opened':
                 raise UserError(_("Order Rejected: The specified session is closed or does not exist."))
            
            if not session.delivery_active:
                 raise UserError(_("Order Rejected: Delivery is currently disabled for this session."))
                 
            if not session.config_id.accept_remote_orders:
                 raise UserError(_("Order Rejected: This POS configuration does not accept remote orders."))
        
        session_id = session.id
        
        # 3. Calculate Totals & Lines
        # We must calculate amount_tax, amount_total, price_subtotal explicitly
        
        total_paid = 0.0
        total_tax = 0.0
        lines_data = []
        
        fiscal_position = self.env['account.fiscal.position'].browse(order_data.get('fiscal_position_id'))
        
        _logger.info("🚀 [create_api_order] Incoming Payload: %s", pformat(order_data))

        for line in order_data['lines']:
            _logger.info("--- 📦 Processing Order Line ---")
            _logger.info("Line Data: %s", pformat(line))
            if not line.get('product_id'):
                _logger.warning("Skipping order line with missing product_id: %s", line)
                continue
                
            product = self.env['product.product'].sudo().browse(int(line['product_id']))
            _logger.info("Product Lookup: ID %s -> Name: %s (Exists: %s)", line['product_id'], product.name, product.exists())
            if not product.exists():
                _logger.error("Product ID %s not found in database. Skipping line.", line['product_id'])
                continue

            qty = line.get('qty', 1)
            price_unit = line.get('price_unit', product.lst_price)
            _logger.info(f"Processing Line - Product: {product.name}, Qty: {qty}, Price: {price_unit}")
            
            # Tax Calculation
            taxes = product.taxes_id.filtered(lambda t: t.company_id.id == session.config_id.company_id.id)
            if fiscal_position:
                taxes = fiscal_position.map_tax(taxes)
            
            # Compute taxes
            tax_res = taxes.compute_all(price_unit, session.currency_id, qty, product=product, partner=self.env['res.partner'].browse(order_data.get('partner_id')))
            
            price_subtotal = tax_res['total_excluded']
            price_subtotal_incl = tax_res['total_included']
            
            current_tax = price_subtotal_incl - price_subtotal
            total_tax += current_tax
            total_paid += price_subtotal_incl

            # --- RECURSIVE COMBO PROCESSING HELPER ---
            def _process_combo_lines(child_data_list):
                processed_children = []
                nonlocal total_tax, total_paid
                
                for c_line in child_data_list:
                    c_product = self.env['product.product'].sudo().browse(int(c_line['product_id']))
                    if not c_product.exists():
                        continue
                    
                    c_qty = c_line.get('qty', 1)
                    c_price_extra = float(c_line.get('extra_price', 0.0))
                    
                    # Compute child taxes
                    c_taxes = c_product.taxes_id.filtered(lambda t: t.company_id.id == session.config_id.company_id.id)
                    if fiscal_position:
                        c_taxes = fiscal_position.map_tax(c_taxes)
                    
                    c_tax_res = c_taxes.compute_all(c_price_extra, session.currency_id, c_qty, product=c_product)
                    c_subtotal = c_tax_res['total_excluded']
                    c_subtotal_incl = c_tax_res['total_included']
                    
                    total_tax += (c_subtotal_incl - c_subtotal)
                    total_paid += c_subtotal_incl

                    # Resolve Attributes (Try PTAV directly, fallback to PAV mapping)
                    ptav_ids = []
                    extra_names = []
                    if c_line.get('attribute_value_ids'):
                        try:
                            val_ids = [int(v) for v in c_line['attribute_value_ids']]
                            _logger.info("🛠️ Resolving child attributes for %s: %s", c_product.name, val_ids)
                            
                            # Check if these are already PTAV IDs for this template
                            valid_ptavs = self.env['product.template.attribute.value'].sudo().search([
                                ('id', 'in', val_ids),
                                ('product_tmpl_id', '=', c_product.product_tmpl_id.id)
                            ])
                            
                            if len(valid_ptavs) == len(val_ids):
                                ptav_ids = valid_ptavs.ids
                                _logger.info("✅ Child IDs are already valid PTAVs")
                            else:
                                # Fallback: Treat as PAV IDs and map to PTAVs
                                mapped_ptavs = self.env['product.template.attribute.value'].sudo().search([
                                    ('product_tmpl_id', '=', c_product.product_tmpl_id.id),
                                    ('product_attribute_value_id', 'in', val_ids)
                                ])
                                ptav_ids = mapped_ptavs.ids
                                _logger.info("📡 Child PAVs mapped to PTAVs: %s", ptav_ids)
                            
                            extra_names = [v.name for v in self.env['product.template.attribute.value'].sudo().browse(ptav_ids)]
                        except Exception as e:
                            _logger.error("🔥 Error resolving child attributes for %s: %s", c_product.name, e)
                    
                    c_display_name = c_product.name
                    if extra_names:
                        c_display_name += f" ({', '.join(extra_names)})"

                    # RECURSIVE STEP: Process grandchildren
                    nested_children = []
                    if c_line.get('combo_line_ids'):
                        nested_children = _process_combo_lines(c_line['combo_line_ids'])

                    processed_children.append((0, 0, {
                        'product_id': c_product.id,
                        'qty': c_qty,
                        'combo_item_id': c_line.get('combo_item_id'),
                        'price_unit': c_price_extra,
                        'price_subtotal': c_subtotal,
                        'price_subtotal_incl': c_subtotal_incl,
                        'full_product_name': c_display_name,
                        'name': c_display_name,
                        'company_id': session.company_id.id,
                        'price_extra': c_price_extra,
                        'tax_ids': [(6, 0, c_taxes.ids)],
                        'attribute_value_ids': [(6, 0, ptav_ids)],
                        'combo_line_ids': nested_children,
                    }))

                return processed_children

            # Extract Combo Lines (Start recursion)
            combo_child_ids = []
            if line.get('combo_line_ids'):
                combo_child_ids = _process_combo_lines(line['combo_line_ids'])

            # Generate full product name including extras/attributes
            ptav_ids = []
            extra_names = []
            # Resolve Parent Attributes (Try PTAV directly, fallback to PAV mapping)
            ptav_ids = []
            extra_names = []
            if line.get('attribute_value_ids'):
                _logger.info("🛠️ Resolving parent attributes for %s: %s", product.name, line['attribute_value_ids'])
                try:
                    val_ids = [int(v) for v in line['attribute_value_ids']]
                    
                    # Check if these are already PTAV IDs for this template
                    valid_ptavs = self.env['product.template.attribute.value'].sudo().search([
                        ('id', 'in', val_ids),
                        ('product_tmpl_id', '=', product.product_tmpl_id.id)
                    ])
                    
                    if len(valid_ptavs) == len(val_ids):
                        ptav_ids = valid_ptavs.ids
                        _logger.info("✅ Parent IDs are already valid PTAVs")
                    else:
                        # Fallback: Treat as PAV IDs and map to PTAVs
                        mapped_ptavs = self.env['product.template.attribute.value'].sudo().search([
                            ('product_tmpl_id', '=', product.product_tmpl_id.id),
                            ('product_attribute_value_id', 'in', val_ids)
                        ])
                        ptav_ids = mapped_ptavs.ids
                        _logger.info("📡 Parent PAVs mapped to PTAVs: %s", ptav_ids)
                    
                    extra_names = [v.name for v in self.env['product.template.attribute.value'].sudo().browse(ptav_ids)]
                except Exception as e:
                    _logger.error("🔥 Error resolving parent attributes for %s: %s", product.name, e)
                
            display_name = product.name
            if extra_names:
                display_name += f" ({', '.join(extra_names)})"

            line_vals = {
                'product_id': product.id,
                'qty': qty,
                'price_unit': price_unit,
                'price_subtotal': price_subtotal,
                'price_subtotal_incl': price_subtotal_incl,
                'tax_ids': [(6, 0, taxes.ids)],
                'full_product_name': display_name,
                'name': display_name,
                'customer_note': line.get('note'),
                'combo_line_ids': combo_child_ids,
                'company_id': session.company_id.id,
                'attribute_value_ids': [(6, 0, ptav_ids)],
            }
            _logger.info("📝 Final Line Vals: %s", pformat(line_vals))
            lines_data.append((0, 0, line_vals))

        amount_total = total_paid # In POS, paid usually equals total
        
        # --- SIMULATION MODE ---
        if order_data.get('simulate'):
             _logger.info(f"SIMULATION_MODE: Returning dict. Price: {amount_total}")
             return {
                 'amount_total': amount_total,
                 'amount_tax': total_tax,
                 'lines': [l[2] for l in lines_data],
                 'currency_symbol': session.currency_id.symbol,
                 'partner_id': order_data.get('partner_id'),
             }
        _logger.info("PERSIST_MODE: Proceeding to database create")

        # Override with provided total if minor rounding diffs (optional safety)
        if order_data.get('amount_paid'):
            # simple validation?
            pass

        # 4. Generate proper order sequences (critical for compliance/auditing)
        pos_reference, tracking_number = session.config_id._get_next_order_refs()
        sequence_number = int(
            session.config_id.order_seq_id
            ._next()
            .removeprefix(session.config_id.order_seq_id.prefix or '')
            .removesuffix(session.config_id.order_seq_id.suffix or '')
        )
        # Order name follows format: "Order XXXXX-XXX-XXXX"
        order_name = f"Order {session.config_id.id:05d}-{session.id:03d}-{sequence_number:04d}"

        # 5. Build Order Values
        # Decisions based on payment mode
        payment_mode = order_data.get('payment_method', 'online')
        is_paid = payment_mode == 'online'
        to_invoice = order_data.get('to_invoice', is_paid)
        
        order_vals = {
            'name': order_name,
            'pos_reference': pos_reference,
            'tracking_number': tracking_number,
            'sequence_number': sequence_number,
            'session_id': session_id,
            'preset_id': self.env['pos.preset'].search([('name', 'ilike', 'Delivery')], limit=1).id or 3,
            'delivery_status': 'received',
            'amount_tax': total_tax,
            'amount_total': amount_total,
            'amount_paid': amount_total if is_paid else 0.0,
            'amount_return': 0.0,
            'partner_id': order_data.get('partner_id'),
            'fiscal_position_id': fiscal_position.id if fiscal_position else False,
            'pricelist_id': session.config_id.pricelist_id.id,
            'company_id': session.config_id.company_id.id,
            'unique_uuid': unique_uuid,
            'is_api_order': True,
            'api_source': order_data.get('source', 'other'),
            'api_customer_name': order_data.get('customer_name'),
            'api_customer_phone': order_data.get('customer_phone'),
            'api_delivery_address': order_data.get('delivery_address'),
            'api_order_notes': order_data.get('notes'),
            'general_customer_note': order_data.get('notes'),
            'state': 'paid' if is_paid else 'draft',
            'to_invoice': to_invoice,
        }

        if is_paid:
            order_vals['payment_ids'] = [[0, 0, {
                'amount': amount_total,
                'payment_method_id': order_data['payment_method_id'],
                'name': uuid.uuid4().hex[:8],
                'company_id': session.config_id.company_id.id,
                # Use standard Odoo card fields
                'card_brand': order_data.get('stripe_card_brand'),
                'card_no': order_data.get('stripe_card_last4'),
                'cardholder_name': order_data.get('stripe_cardholder_name'),
                'transaction_id': order_data.get('stripe_transaction_id'),
            }]]
        
        # Determine accounting payment method for invoice
        invoice_payment_method_id = False
        if is_paid:
            payment_method = self.env['pos.payment.method'].browse(order_data['payment_method_id'])
            # Most POS payment methods have a journal with inbound methods
            if payment_method.journal_id and payment_method.journal_id.inbound_payment_method_line_ids:
                 # Prefer anything named 'stripe' or 'bank'
                 pm_lines = payment_method.journal_id.inbound_payment_method_line_ids
                 best_pm = pm_lines.filtered(lambda l: 'stripe' in l.name.lower()) or \
                           pm_lines.filtered(lambda l: 'bank' in l.name.lower()) or \
                           pm_lines[0]
                 invoice_payment_method_id = best_pm.id

        try:
            # Create the order first
            order = self.sudo().create(order_vals)
            _logger.info(f"Main Order Record Created: {order.id}")
            
            # Create lines manually to ensure order_id is correctly set (Flattened approach)
            for line_tuple in lines_data:
                line_vals = line_tuple[2]
                combo_sub_lines = line_vals.pop('combo_line_ids', [])
                line_vals['order_id'] = order.id
                parent_line = self.env['pos.order.line'].sudo().create(line_vals)
                
                for combo_tuple in combo_sub_lines:
                    combo_vals = combo_tuple[2]
                    combo_vals['order_id'] = order.id
                    combo_vals['combo_parent_id'] = parent_line.id
                        
                    self.env['pos.order.line'].sudo().create(combo_vals)

            # Generate Invoice if requested
            if to_invoice:
                _logger.info(f"Generating invoice for order {order.name}")
                # Skip PDF generation to avoid wkhtmltopdf dependency errors in local environments
                order.with_context(generate_pdf=False).action_pos_order_invoice()
                
                # After invoice creation, set the accounting payment method if we found one
                if order.account_move and invoice_payment_method_id:
                    # 'payment_method_line_id' is the standard field in Odoo 17+ for inbound payments
                    # but on account.move, it might be 'payment_reference' or handled by the reconciliation.
                    # Image 4 shows a specific 'Payment Method' label under Accounting.
                    # We try to write to the move if the field exists.
                    try:
                        order.account_move.write({'payment_method_line_id': invoice_payment_method_id})
                    except:
                        pass

            # 6. Trigger real-time sync in POS using native Odoo 19 notification pattern
            # pos.config inherits pos.bus.mixin, which sends to the config's access_token channel.
            # The POS frontend subscribes to this channel automatically.
            try:
                # Use session.config_id directly — this is the EXACT same config whose
                # access_token the POS frontend subscribed to via getOnNotified(bus, odoo.access_token).
                config = session.config_id
                config._ensure_access_token()
                _logger.info("=== NEW_REMOTE_ORDER NOTIFICATION ===")
                _logger.info("Order ID: %s, Config: %s (id=%s), Token: %s", 
                             order.id, config.name, config.id, config.access_token)
                
                notification_payload = {
                    'order_id': order.id,
                    'pos_reference': order.pos_reference,
                    'amount_total': order.amount_total,
                    'source': 'online'
                }
                
                # Single notification via _notify (same pattern as CLOSING_SESSION)
                config._notify('NEW_REMOTE_ORDER', notification_payload)
                _logger.info("✅ NEW_REMOTE_ORDER notification sent for order %s", order.id)
                    
            except Exception as notify_err:
                _logger.error("❌ Failed to send NEW_REMOTE_ORDER notification: %s", str(notify_err), exc_info=True)

            return order

        except Exception as e:
            _logger.error(f"API Order Creation Failed: {e}")
            raise ValidationError(f"System Error: {str(e)}")

    # NOTE: DO NOT override _load_pos_data_fields for pos.order in Odoo 19 Community.
    # In Odoo 19, if _load_pos_data_fields returns an empty list (default), 
    # the system automatically loads ALL fields (approx 100+), including custom ones.
    # Returning a non-empty list here blocks this behavior and causes the POS crash 
    # as core fields like 'lines' disappear from the frontend model.

    @api.model
    def notify_new_order(self, order_id):
        """Explicitly notify the POS frontend about a new remote order.
        Called from Next.js fulfillment after order creation as a backup notification."""
        _logger.info("notify_new_order called for order_id=%s", order_id)
        try:
            order = self.sudo().browse(order_id)
            if not order.exists():
                _logger.error("notify_new_order: order %s not found", order_id)
                return False
            
            session = order.session_id
            config = session.config_id
            config._ensure_access_token()
            token = config.access_token
            
            payload = {
                'order_id': order.id,
                'pos_reference': order.pos_reference,
                'amount_total': order.amount_total,
                'source': 'online'
            }
            
            _logger.info("notify_new_order: Sending to config %s (token=%s)", config.name, token)
            
            # Send via _notify (high-level)
            config._notify('NEW_REMOTE_ORDER', payload)
            
            # Also send direct bus message (low-level backup) 
            self.env['bus.bus']._sendone(token, f"{token}-NEW_REMOTE_ORDER", payload)
            
            _logger.info("✅ notify_new_order: Both notifications sent for order %s", order_id)
            return True
        except Exception as e:
            _logger.error("❌ notify_new_order failed: %s", str(e), exc_info=True)
            return False


    @api.model
    def claim_remote_print(self, order_id, session_id):
        # ... (Existing claim logic) ...
        # Copied from previous step to keep file complete
        order = self.browse(order_id)
        if not order.exists():
            return False
        if order.is_remote_printed:
            return False
        if order.remote_printer_lock and order.remote_printer_lock.id != session_id:
            return False
        if not order.remote_printer_lock:
             order.write({
                 'remote_printer_lock': session_id,
                 'is_remote_printed': True
             })
             return True
        return False

    @api.model
    def update_delivery_status(self, order_id=None, new_status=None):
        """
        Update delivery status for an order and broadcast to POS.
        Can be called as @api.model (API) or as an object method (Backend UI).
        """
        if not new_status:
            new_status = self.env.context.get('new_status')
            
        valid_statuses = ['received', 'preparing', 'ready', 'on_the_way', 'delivered', 'cancelled']
        if new_status not in valid_statuses:
            raise ValidationError(f"Invalid status: {new_status}. Must be one of: {valid_statuses}")
        
        if order_id:
            # API call
            orders = self.sudo().browse(order_id)
        else:
            # Object call from backend
            orders = self.sudo()

        for order in orders:
            if not order.exists():
                _logger.warning(f"Order {order.id} not found during status update")
                continue
            
            old_status = order.delivery_status
            order.write({'delivery_status': new_status})
            
            # Broadcast status change to POS session
            if order.session_id:
                channel = order.session_id._get_bus_channel_name()
                _logger.info("Broadcasting DELIVERY_STATUS_CHANGE to channel %s for order %s", channel, order.pos_reference)
                self.env['bus.bus']._sendone(
                    channel,
                    'DELIVERY_STATUS_CHANGE',
                    {
                        'order_id': order.id,
                        'old_status': old_status,
                        'new_status': new_status,
                        'pos_reference': order.pos_reference,
                    }
                )
            
            _logger.info(f"Order {order.pos_reference} status changed: {old_status} -> {new_status}")
        return True
    def _get_invoice_lines_values(self, line_values, pos_line, move_type):
        """
        OVERRIDE: Odoo 19 treats 'combo' products as Sections (display_type='line_section')
        which drops the price and tax data. We must force them to be regular lines
        if they have a price > 0, otherwise the invoice total will be wrong.
        ALSO: Ensure display_type is NEVER null to avoid DB constraint errors.
        """
        res = super()._get_invoice_lines_values(line_values, pos_line, move_type)
        
        # Ensure display_type is never Null/False for product lines to satisfy DB NotNull constraint
        if not res.get('display_type'):
            res['display_type'] = 'product'
            
        # If it was converted to a section but has a price, revert it to a normal line
        if res.get('display_type') == 'line_section' and line_values['price_unit'] != 0:
            # Re-apply standard line values
            qty_sign = -1 if (
                (move_type == 'out_invoice' and pos_line.order_id.is_refund)
                or (move_type == 'out_refund' and not pos_line.order_id.is_refund)
            ) else 1
            
            res.update({
                'display_type': 'product', # Force 'product' instead of False/None to satisfy DB
                'product_id': line_values['product_id'].id,
                'quantity': qty_sign * line_values['quantity'],
                'discount': line_values['discount'],
                'price_unit': line_values['price_unit'],
                'name': line_values['name'],
                'tax_ids': [(6, 0, line_values['tax_ids'].ids)],
                'product_uom_id': line_values['uom_id'].id,
                'extra_tax_data': self.env['account.tax']._export_base_line_extra_tax_data(line_values),
            })
            
        return res
