/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";

patch(FloorScreen.prototype, {
    async onClickTable(table, ev) {
        // Intercept table click for bookings
        if (!this.pos.isEditMode && table.table_resource_id) {
            const bookings = await this.pos.data.call(
                "table.booking",
                "search_read",
                [[
                    ["resource_ids", "in", [table.table_resource_id[0]]],
                    ["status", "=", "confirmed"],
                    ["start_time", ">=", this._formatDate(new Date(Date.now() - 3600000))],
                    ["start_time", "<=", this._formatDate(new Date(Date.now() + 3600000))]
                ]],
                { fields: ["customer_name", "party_size"], limit: 1 }
            );

            if (bookings.length > 0) {
                const booking = bookings[0];
                const { confirmed, payload } = await this.dialog.add(SelectionPopup, {
                    title: `Booking: ${booking.customer_name} (${booking.party_size} pax)`,
                    list: [
                        { id: 'checkin', label: 'Check-In', item: 'checkin' },
                        { id: 'noshow', label: 'No-Show', item: 'noshow' },
                        { id: 'open', label: 'Just Open (Regular Order)', item: 'open' },
                    ],
                });

                if (confirmed) {
                    if (payload === 'checkin') {
                        await this.pos.data.call("table.booking", "action_check_in", [booking.id]);
                        await this.pos.setTableFromUi(table);
                        return;
                    } else if (payload === 'noshow') {
                        await this.pos.data.call("table.booking", "action_no_show", [booking.id]);
                        await this._checkAllBookings();
                        return;
                    }
                }
            }
        }

        return super.onClickTable(...arguments);
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
