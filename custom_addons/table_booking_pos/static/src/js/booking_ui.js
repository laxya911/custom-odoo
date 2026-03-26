/** @odoo-module */

import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

import { registry } from "@web/core/registry";

// 1. Define the Screen
export class BookingsScreen extends Component {
    static storeOnOrder = false;
    static template = "table_booking_pos.BookingsScreen";
    static props = {
        title: { type: String, optional: true },
        key: { type: String, optional: true },
        bookings: { type: Array, optional: true },
        close: { type: Function, optional: true },
        confirm: { type: Function, optional: true },
        cancel: { type: Function, optional: true },
    };

    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
        this.state = useState({
            bookings: [],
            isLoading: false,
            searchWord: "",
        });

        this.loadBookings();
    }

    get filteredBookings() {
        const search = (this.state.searchWord || "").toLowerCase();
        if (!search) return this.state.bookings;
        return this.state.bookings.filter(b => 
            (b.customer_name && b.customer_name.toLowerCase().includes(search)) ||
            (b.name && b.name.toLowerCase().includes(search)) ||
            (b.customer_phone && b.customer_phone.includes(search))
        );
    }

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

    async loadBookings() {
        this.state.isLoading = true;
        console.log("POS Bookings: Loading bookings...");
        try {
            const now = new Date();
            // Expanded range: Yesterday to Tomorrow to rule out timezone shifts
            const start = new Date(now.getTime() - 24 * 3600000);
            const end = new Date(now.getTime() + 24 * 3600000);

            const domain = [
                ["start_time", ">=", this._formatDate(start)],
                ["start_time", "<=", this._formatDate(end)],
                ["status", "in", ["confirmed", "checked_in", "no_show"]]
            ];
            
            console.log("POS Bookings: Requesting domain", domain);

            const bookings = await this.pos.data.call(
                "table.booking",
                "search_read",
                [domain],
                { 
                    fields: ["name", "customer_name", "customer_phone", "customer_email", "party_size", "start_time", "status", "resource_ids", "table_names"],
                    order: "start_time asc"
                }
            );
            
            console.log("POS Bookings: Received", bookings.length, "bookings", bookings);
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

    formatTime(timeStr) {
        if (!timeStr) return "";
        try {
            // Expecting YYYY-MM-DD HH:mm:ss in UTC from server
            const date = new Date(timeStr.replace(' ', 'T') + 'Z');
            const h = date.getHours();
            const m = String(date.getMinutes()).padStart(2, '0');
            const ampm = h >= 12 ? 'PM' : 'AM';
            const h12 = h % 12 || 12;
            return `${h12}:${m} ${ampm}`;
        } catch (e) {
            return timeStr;
        }
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

    back() {
        this.pos.navigate("FloorScreen");
    }
}

// Registration for Odoo 19/20 navigation
registry.category("pos_screens").add("BookingsScreen", { component: BookingsScreen });
registry.category("pos_pages").add("BookingsScreen", {
    name: "BookingsScreen",
    component: BookingsScreen,
    route: `/pos/ui/${odoo.pos_config_id}/bookings`,
});

// 2. Define the Button
export class BookingsButton extends Component {
    static template = "table_booking_pos.BookingsButton";
    static props = {};

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
    }

    get isActive() {
        return this.pos.mainScreen && this.pos.mainScreen.component && this.pos.mainScreen.component.name === "BookingsScreen";
    }

    onClick(ev) {
        if (ev && ev.stopPropagation) ev.stopPropagation();
        this.pos.navigate("BookingsScreen");
    }
}

// 4. Navbar Patch to handle active state for Bookings
patch(Navbar.prototype, {
    get mainButton() {
        if (this.pos.router.state.current === 'BookingsScreen') {
            return 'bookings';
        }
        return super.mainButton;
    }
});

// 3. Patch the Navbar - Ensure components object exists
if (!Navbar.components) {
    Navbar.components = {};
}
patch(Navbar, {
    components: { ...Navbar.components, BookingsButton },
});
