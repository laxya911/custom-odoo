# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PosTable(models.Model):
    _inherit = 'restaurant.table'

    table_resource_id = fields.Many2one(
        'table.resource',
        string='Linked Booking Resource',
        help="Link this POS table to a physical booking resource for status synchronization."
    )

    @api.model
    def action_sync_booking_resources(self, pos_config_id=None):
        """
        Synchronizes restaurant.table records with table.resource records so that
        all tables on the floor plan are immediately selectable for booking.
        Also guarantees an active table.booking.config exists for the POS.
        """
        domain = []
        if pos_config_id:
            domain = [('floor_id.pos_config_ids', 'in', [pos_config_id])]
        tables = self.search(domain)
        Resource = self.env['table.resource'].sudo()
        Config = self.env['table.booking.config'].sudo()

        # Ensure active config exists
        config_domain = [('active_booking', '=', True)]
        if pos_config_id:
            config_domain = [('pos_config_id', '=', pos_config_id)]
        cfg = Config.search(config_domain, limit=1)
        if not cfg:
            Config.create({
                'name': 'POS Table Booking',
                'active_booking': True,
                'pos_config_id': pos_config_id or False,
                'max_party_size': 20,
            })

        for table in tables:
            if not table.table_resource_id or not table.table_resource_id.exists():
                t_name = f"Table {table.table_number or table.name or table.id}"
                resource = Resource.search([('pos_table_id', '=', table.id)], limit=1)
                if not resource:
                    resource = Resource.create({
                        'name': t_name,
                        'capacity': table.seats or 2,
                        'pos_table_id': table.id,
                        'active': True,
                    })
                table.sudo().write({'table_resource_id': resource.id})
        return True
