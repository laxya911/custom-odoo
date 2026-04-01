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
                    ["status", "in", ["confirmed", "checked_in"]],
                    ["start_time", ">=", this._formatDate(new Date(Date.now() - 3600 * 2 * 1000))], // 2 hours ago
                    ["start_time", "<=", this._formatDate(new Date(Date.now() + 3600 * 4 * 1000))]  // 4 hours ahead
                ]],
                { fields: ["customer_name", "party_size", "status"], limit: 1 }
            );

            if (bookings.length > 0) {
                const booking = bookings[0];
                const actionList = [];
                
                if (booking.status === 'confirmed') {
                    actionList.push({ id: 'checkin', label: 'Check-In', item: 'checkin' });
                    actionList.push({ id: 'noshow', label: 'No-Show', item: 'noshow' });
                } else if (booking.status === 'checked_in') {
                    actionList.push({ id: 'complete', label: 'Mark as Completed', item: 'complete' });
                }
                
                actionList.push({ id: 'open', label: 'Open Regular Order', item: 'open' });

                const { confirmed, payload } = await this.dialog.add(SelectionPopup, {
                    title: `Reservation: ${booking.customer_name} (${booking.party_size} pax)`,
                    list: actionList,
                });

                if (confirmed) {
                    if (payload === 'checkin') {
                        await this.pos.data.call("table.booking", "action_check_in", [[booking.id]]);
                        await this.pos.setTableFromUi(table);
                        return;
                    } else if (payload === 'noshow') {
                        await this.pos.data.call("table.booking", "action_no_show", [[booking.id]]);
                        return;
                    } else if (payload === 'complete') {
                        await this.pos.data.call("table.booking", "action_complete", [[booking.id]]);
                        return;
                    }
                }
            }
        }

        return super.onClickTable(...arguments);
    },

    _formatDate(date) {
        return date.toISOString().replace('T', ' ').substring(0, 19);
    }
});
