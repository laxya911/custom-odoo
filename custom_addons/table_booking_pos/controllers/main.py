# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.tools import file_open
from odoo.addons.point_of_sale.controllers.main import PosController

class TableBookingPosController(PosController):

    @http.route('/pos/service-worker.js', type='http', auth='user')
    def pos_web_service_worker(self):
        """Override the default service worker to use our custom one with 206 fix."""
        response = request.make_response(
            self._get_pos_service_worker(),
            [
                ('Content-Type', 'text/javascript'),
                ('Service-Worker-Allowed', '/pos'),
            ],
        )
        return response

    def _get_pos_service_worker(self):
        """Serve our custom service worker from the table_booking_pos module."""
        try:
            with file_open('table_booking_pos/static/src/js/service_worker.js') as f:
                return f.read()
        except Exception:
            # Fallback to core if our file is missing for any reason
            return super()._get_pos_service_worker()
