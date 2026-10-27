# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class PosOrderApiController(http.Controller):

    @http.route('/api/pos/order/create', type='jsonrpc', auth='public', methods=['POST'])
    def create_order(self, **params):
        """
        JSON-RPC 2.0 endpoint for creating orders from online storefront.
        Allows public online ordering and tax/price simulation with sudo elevation.
        """
        try:
            order_model = request.env['pos.order'].sudo()
            result = order_model.create_api_order(params)
            if isinstance(result, dict) and 'amount_total' in result:
                # Simulation mode returns calculation dictionary directly
                return result
            return {
                'status': 'success',
                'order_id': result.id,
                'pos_ref': result.pos_reference
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/pos/order/update_status', type='jsonrpc', auth='public', methods=['POST'])
    def update_order_status(self, order_id, status):
        """
        Update delivery status via API.
        """
        try:
            request.env['pos.order'].sudo().update_delivery_status(order_id=order_id, new_status=status)
            return {
                'status': 'success',
                'message': f'Order {order_id} updated to {status}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    @http.route('/api/pos/session/status', type='jsonrpc', auth='public', methods=['POST'])
    def session_status(self, config_id=False):
        """ Check if a specific or any delivery session is active """
        domain = [('state', '=', 'opened')]
        if config_id:
            domain.append(('config_id', '=', config_id))

        session = request.env['pos.session'].sudo().search(domain, limit=1)
        if not session:
            return {'status': 'inactive', 'message': 'No open session found'}

        return {
            'status': 'active',
            'session_id': session.id,
            'delivery_active': session.delivery_active and session.config_id.accept_remote_orders,
            'config_name': session.config_id.name
        }

    @http.route(['/api/pos/product/image/<string:model>/<int:id>', '/api/pos/product/image/<int:id>'], type='http', auth='public', methods=['GET'], cors='*')
    def get_pos_product_image(self, id, model='product.template', **kwargs):
        """
        Public HTTP endpoint to stream product images for online storefront.
        Uses sudo elevation so it works for POS products regardless of is_published state.
        """
        if model not in ['product.template', 'product.product']:
            model = 'product.template'
        
        record = request.env[model].sudo().browse(id)
        if not record.exists():
            return request.not_found()
            
        raw = record.image_1920
        if not raw and model == 'product.product' and record.product_tmpl_id:
            raw = record.product_tmpl_id.image_1920
            
        if not raw:
            return request.not_found()
            
        data = bytes(raw)
        content_type = 'image/png'
        if data.startswith(b'\xff\xd8'):
            content_type = 'image/jpeg'
        elif data.startswith(b'GIF'):
            content_type = 'image/gif'
        elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            content_type = 'image/webp'
            
        return request.make_response(data, [
            ('Content-Type', content_type),
            ('Content-Length', str(len(data))),
            ('Cache-Control', 'public, max-age=86400'),
        ])
