/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { onWillStart } from "@odoo/owl";

patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.tableBookings = {};

        onWillStart(async () => {
            await this._checkAllBookings();
        });
    },

    async _checkAllBookings() {
        if (!this.activeTables || this.activeTables.length === 0) return;
        
        const resourceIds = this.activeTables.map(t => t.table_resource_id && t.table_resource_id[0]).filter(Boolean);
        if(!resourceIds.length) return;

        try {
            const bookings = await this.pos.data.call(
                "table.booking",
                "search_read",
                [[
                    ["resource_ids", "in", resourceIds],
                    ["status", "in", ["confirmed", "checked_in"]],
                    ["start_time", ">=", this._formatDate(new Date(Date.now() - 2 * 3600000))],
                    ["start_time", "<=", this._formatDate(new Date(Date.now() + 4 * 3600000))]
                ]],
                { fields: ["customer_name", "party_size", "start_time", "status", "resource_ids"] }
            );

            const newTableBookings = {};
            const nowTs = Date.now();

            for (const table of this.activeTables) {
                if (!table.table_resource_id) continue;
                const resourceId = table.table_resource_id[0];
                
                // Find booking starting within 1 hour or already checked in
                const activeBooking = bookings.find(b => {
                    if (!b.resource_ids.includes(resourceId)) return false;
                    if (b.status === 'checked_in') return true;
                    // Parse "YYYY-MM-DD HH:mm:ss" UTC
                    const startTs = new Date(b.start_time.replace(' ', 'T') + 'Z').getTime();
                    return startTs < (nowTs + 3600000) && startTs > (nowTs - 1800000);
                });

                if (activeBooking) {
                    newTableBookings[table.id] = activeBooking;
                }
            }
            this.state.tableBookings = newTableBookings;

        } catch (e) {
            console.warn("Failed to check booking status for tables", e);
        }
    },

    _formatDate(date) {
        const pad = (num) => String(num).padStart(2, '0');
        const Y = date.getFullYear();
        const M = pad(date.getMonth() + 1);
        const D = pad(date.getDate());
        const h = pad(date.getHours());
        const m = pad(date.getMinutes());
        const s = pad(date.getSeconds());
        return `${Y}-${M}-${D} ${h}:${m}:${s}`;
    }
});
