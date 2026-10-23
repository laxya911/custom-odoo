/** @odoo-module */

import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { patch } from "@web/core/utils/patch";

export class BookingsButton extends Component {
    static template = "table_booking_pos.BookingsButton";
    static props = {};

    setup() {
        this.pos = usePos();
    }

    get isActive() {
        return this.pos.mainScreen.name === 'BookingsScreen';
    }

    get count() {
        // We could fetch today's booking count here if we wanted a badge
        return 0;
    }

    onClick() {
        this.pos.navigate("BookingsScreen");
    }
}

patch(Navbar, {
    components: { ...Navbar.components, BookingsButton },
});
