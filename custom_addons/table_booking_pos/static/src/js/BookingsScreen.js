/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class BookingsScreen extends Component {
    static template = "table_booking_pos.BookingsScreen";
    static props = {};

    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
        this.dialog = useService("dialog");
        this.state = useState({
            bookings: [],
            isLoading: true,
            filter: 'today'
        });

        onWillStart(async () => {
            await this.loadBookings();
        });
    }

    async loadBookings() {
        this.state.isLoading = true;
        try {
            const domain = [
                ["start_time", ">=", moment().startOf('day').format('YYYY-MM-DD HH:mm:ss')],
                ["start_time", "<=", moment().endOf('day').format('YYYY-MM-DD HH:mm:ss')],
                ["state", "in", ["confirmed", "checked_in", "no_show"]]
            ];
            
            const bookings = await this.pos.data.call(
                "table.booking",
                "search_read",
                [domain],
                { fields: ["name", "customer_name", "party_size", "start_time", "state", "resource_ids", "table_names"] }
            );
            this.state.bookings = bookings;
        } catch (e) {
            console.error("Failed to load bookings:", e);
        } finally {
            this.state.isLoading = false;
        }
    }

    async checkIn(bookingId) {
        try {
            this.ui.block();
            await this.pos.data.call("table.booking", "action_check_in", [[bookingId]]);
            await this.loadBookings();
        } finally {
            this.ui.unblock();
        }
    }

    async noShow(bookingId) {
        try {
            this.ui.block();
            await this.pos.data.call("table.booking", "action_no_show", [[bookingId]]);
            await this.loadBookings();
        } finally {
            this.ui.unblock();
        }
    }

    close() {
        this.pos.navigate("FloorScreen");
    }

    formatTime(timeStr) {
        return moment(timeStr).format("hh:mm A");
    }

    getBookingStatus(state) {
        const statuses = {
            'confirmed': _t('Confirmed'),
            'checked_in': _t('Checked In'),
            'no_show': _t('No Show'),
            'cancelled': _t('Cancelled'),
            'draft': _t('Draft')
        };
        return statuses[state] || state;
    }
}

registry.category("pos_pages").add("BookingsScreen", {
    component: BookingsScreen,
    path: "/bookings",
    match: (url) => url === "BookingsScreen",
});
