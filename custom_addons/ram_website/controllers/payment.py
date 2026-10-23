import pprint
import werkzeug

from odoo import http, _
from odoo.http import request
from odoo.addons.payment import utils as payment_utils
import logging
import json
import urllib.parse

_logger = logging.getLogger(__name__)

class RamPaymentController(http.Controller):
    
    @http.route('/ram/payment/providers', type='json', auth='public')
    def get_providers(self):
        """ Return available payment providers for configuration """
        providers = request.env['payment.provider'].sudo().search([
            ('state', '!=', 'disabled'),
            ('company_id', '=', request.env.company.id)
        ])
        return [{
            'id': p.id,
            'name': p.name,
            'code': p.code,
            'image_url': f"/web/image/payment.provider/{p.id}/image_128",
            'inline_form_view_id': p.inline_form_view_id.id if p.inline_form_view_id else False
        } for p in providers]

    @http.route('/ram/payment/transaction/create', type='json', auth='public')
    def create_transaction(self, amount, provider_id, currency_id=False, partner_id=False, flow='direct'):
        # 1. Validate inputs
        if not amount or not provider_id:
             return {'error': 'Invalid parameters'}
             
        provider = request.env['payment.provider'].sudo().browse(int(provider_id))
        if not provider.exists():
             return {'error': 'Provider not found'}
             
        # 2. Get Partner
        if not partner_id:
            partner = request.env.user.partner_id
            if not partner or request.env.user._is_public():
                  return {'error': 'Partner required'}
        return {} # Placeholder as this route's logic was largely replaced by get_payment_url

    @http.route('/ram/payment/get_url', type='json', auth='user')
    def get_payment_url(self, amount, currency_id=False):
        """
        Generates a signed URL for the standard Odoo payment page.
        """
        user = request.env.user
        partner = user.partner_id
        
        # Ensure currency
        if not currency_id:
            currency_id = request.env.company.currency_id.id
            
        currency = request.env['res.currency'].browse(int(currency_id))
        
        # Generate Reference
        reference = request.env['payment.transaction'].sudo()._compute_reference('stripe', prefix='RAM-WEB')
        
        # Generate Access Token
        access_token = payment_utils.generate_access_token(partner.id, float(amount), currency.id)
        
        # Construct URL
        query = {
            'reference': reference,
            'amount': float(amount),
            'currency_id': currency.id,
            'partner_id': partner.id,
            'access_token': access_token,
            'company_id': request.env.company.id,
        }
        from werkzeug.urls import url_encode
        return {
            'url': f"/payment/pay?{url_encode(query)}",
            'reference': reference
        }

    @http.route('/ram/payment/finalize', type='http', auth='user', website=True)
    def ram_finalize_payment(self, reference, **kwargs):
        """
        Called after successful payment.
        """
        tx = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
        
        if not tx:
             return request.redirect('/ram?error=transaction_not_found')
            
        if tx.state not in ['done', 'authorized', 'pending']:
            return request.redirect('/ram?error=payment_failed')
            
        cart = request.env['ram.website.cart'].sudo().get_cart_for_partner(request.env.user.partner_id.id)
        
        existing = request.env['pos.order'].sudo().search([('unique_uuid', '=', reference)], limit=1)
        if existing:
             return request.redirect(f'/ram/order/success/{existing.unique_uuid}')

        if not cart or not cart.line_ids:
             return request.redirect('/ram?error=cart_empty_after_payment')

        # Find active session
        session = request.env['pos.session'].sudo().search([
            ('state', '=', 'opened'),
            ('delivery_active', '=', True),
            ('config_id.accept_remote_orders', '=', True)
        ], limit=1)
        
        if not session:
            return request.redirect('/ram?error=no_active_pos_session')

        # Convert Cart to Order Data
        pos_lines = []
        for line in cart.line_ids:
            variation = {}
            if line.variation_data:
                try:
                    variation = json.loads(line.variation_data)
                except:
                    pass
            
            pos_lines.append({
                'product_id': line.product_id.id,
                'qty': line.qty,
                'price_unit': line.price_unit,
                'note': line.customer_note,
                'combo_line_ids': variation.get('combo_line_ids', []),
                'attribute_value_ids': variation.get('attribute_value_ids', []),
            })

        pos_pm = session.config_id.payment_method_ids.filtered(lambda m: not m.is_cash_count)
        payment_method_id = pos_pm[0].id if pos_pm else (session.config_id.payment_method_ids[:1].id or 1)

        order_data = {
            'uuid': tx.reference,
            'session_id': session.id,
            'lines': pos_lines,
            'partner_id': cart.partner_id.id,
            'customer_name': cart.partner_id.name,
            'customer_phone': cart.partner_id.phone,
            'customer_email': cart.partner_id.email,
            'source': 'native_web',
            'payment_method': 'online',
            'payment_method_id': payment_method_id,
        }

        _logger.info("Finalizing payment for reference %s. Creating POS order...", reference)
        try:
            order = request.env['pos.order'].sudo().create_api_order(order_data)
            _logger.info("POS Order created successfully: %s (ID: %s, UUID: %s)", order.pos_reference, order.id, order.unique_uuid)
            
            # 1. Invoice
            try:
                order.action_pos_order_invoice()
                _logger.info("Invoice generated for order %s", order.name)
            except Exception as inv_e:
                _logger.error(f"Failed to generate invoice: {inv_e}")

            # 2. Clean Cart
            cart.sudo().unlink()
            
            redirect_url = f'/ram/order/success/{order.unique_uuid}'
            _logger.info("Redirecting user to: %s", redirect_url)
            return request.redirect(redirect_url)
             
        except Exception as e:
            _logger.exception("Finalize Failed")
            error_msg = urllib.parse.quote(str(e))
            return request.redirect(f'/ram?error={error_msg}')

    @http.route('/ram/order/success/<string:uuid>', type='http', auth='public', website=True)
    def ram_order_success_page(self, uuid, **kwargs):
        order = request.env['pos.order'].sudo().search([('unique_uuid', '=', uuid)], limit=1)
        if not order:
            return request.redirect('/ram')
            
        return request.render('ram_website.ram_order_success_page', {'order': order})

    @http.route('/ram/payment/transaction/result', type='json', auth='public')
    def payment_result(self, reference):
         tx = request.env['payment.transaction'].sudo().search([('reference', '=', reference)], limit=1)
         if not tx:
              return {'error': 'Transaction not found'}
              
         return {
             'state': tx.state,
             'is_post_processed': tx.is_post_processed,
             'last_state_change': str(tx.last_state_change),
         }
