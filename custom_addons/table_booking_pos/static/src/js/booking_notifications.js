/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);

        if (!this.bus || !this.data) return;

        // Subscribe to new table bookings
        try {
            if (this.config && this.config.accept_table_bookings) {
                this.data.connectWebSocket("TABLE_BOOKING_NEW", (payload) => {
                    this._onNewTableBooking(payload);
                });
                console.log("POS Table Booking: Listening for TABLE_BOOKING_NEW");
            }
        } catch (err) {
            console.error("Table Booking POS: Failed to initialize listener:", err);
        }
    },

    async _onNewTableBooking(payload) {
        console.log("📅 New Table Booking Signal:", payload);
        
        // 1. Play sound
        try {
            if (this.sound && typeof this.sound.play === 'function') {
                this.sound.play("order-receive-tone");
            } else {
                const audio = new Audio("/point_of_sale/static/src/sounds/notification");
                audio.play().catch(e => {});
            }
        } catch (e) {}

        // 2. Show toast
        if (this.notification) {
            this.notification.add(
                _t("New Booking: %s for %s guests", payload.customer_name, payload.party_size),
                {
                    title: _t("📅 New Reservation!"),
                    type: "info",
                    sticky: true,
                    buttons: [
                        {
                            name: _t("View Booking"),
                            onClick: () => {
                                // Standard Odoo 19/20 navigation
                                if (typeof this.navigate === 'function') {
                                    this.navigate('BookingsScreen');
                                } else {
                                    this.close(); // Fallback to current main screen
                                }
                            },
                            primary: true,
                        }
                    ],
                }
            );
        }

        // 3. Trigger a reload of booking status for linked tables
        // In a real implementation, we might want to fetch confirmed bookings for today
        // and update the table status locally.
        if (this.env && this.env.bus) {
            this.env.bus.trigger('table-booking-update');
        } else if (this.bus) {
            this.bus.trigger('table-booking-update');
        }
    }
});
