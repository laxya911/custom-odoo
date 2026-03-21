/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setup() {
        try {
            await super.setup(...arguments);
        } catch (setupErr) {
            console.error("remote_print: Original PosStore setup failed!", setupErr);
        }

        // Safety: Ensure this.bus and this.data are available
        if (!this.bus || !this.data) {
             console.error("remote_print: bus or data service missing on PosStore!");
             return;
        }

        // Track processed order IDs to prevent duplicate notifications
        this._processedRemoteOrders = new Set();

        try {
            if (this.config && this.config.accept_remote_orders) {
                // Subscribe using the native connectWebSocket pattern (token-prefixed channel)
                // This is the same pattern Odoo uses for CLOSING_SESSION in pos_store.js
                this.data.connectWebSocket("NEW_REMOTE_ORDER", (payload) => {
                    this._onNewRemoteOrder(payload);
                });
                console.log("POS Remote Print: Listening for NEW_REMOTE_ORDER via connectWebSocket");
            }
        } catch (err) {
            console.error("remote_print: Failed to initialize remote order printing listener:", err);
        }
    },

    async _onNewRemoteOrder(payload) {
        console.log("🚀 Remote Order Signal:", payload);
        
        try {
            const orderId = payload.order_id;
            
            // Deduplicate: Skip if we already processed this order
            if (this._processedRemoteOrders && this._processedRemoteOrders.has(orderId)) {
                console.log(`⏭️ Order ${orderId} already processed, skipping duplicate notification`);
                return;
            }
            // Mark as processed
            if (this._processedRemoteOrders) {
                this._processedRemoteOrders.add(orderId);
                // Clean up old entries after 60 seconds
                setTimeout(() => this._processedRemoteOrders?.delete(orderId), 60000);
            }

            // === 1. PLAY NOTIFICATION SOUND ===
            try {
                if (this.sound && typeof this.sound.play === 'function') {
                    // Standard Odoo 19 asset for new orders
                    this.sound.play("order-receive-tone");
                    console.log("🔔 Sound 'order-receive-tone' played via PosStore");
                } else {
                    // Fallback: use notification sound without extension
                    const audio = new Audio("/point_of_sale/static/src/sounds/notification");
                    audio.volume = 1.0;
                    audio.play().catch(e => console.warn("🔔 Fallback audio play failed:", e));
                    console.log("🔔 Sound played via fallback 'notification' request");
                }
            } catch (soundErr) {
                console.warn("🔔 Sound play failed:", soundErr.message);
            }

            // === 2. SHOW TOAST NOTIFICATION ===
            if (this.notification) {
                try {
                    this.notification.add(
                        `New Online Order: ${payload.pos_reference || '#' + orderId}`,
                        {
                            title: "🔔 New Order Received!",
                            type: "success",
                            sticky: true,
                            // Odoo 19/Owl standard for adding buttons to notifications
                            buttons: [
                                {
                                    name: "View Order",
                                    onClick: () => {
                                        console.log("🚀 Notification button clicked for order:", orderId);
                                        if (this.navigate) {
                                            // 1. Try to find the "Delivery" preset
                                            let deliveryPreset = null;
                                            try {
                                                if (this.models && this.models["pos.preset"]) {
                                                    deliveryPreset = this.models["pos.preset"].find(p => 
                                                        p.name.toLowerCase() === "delivery"
                                                    );
                                                }
                                            } catch (e) {
                                                console.warn("⚠️ Failed to find delivery preset:", e);
                                            }

                                            // 2. Navigate to TicketScreen (Odoo 19 order management)
                                            // We use stateOverride to set the initial filters
                                            this.navigate('TicketScreen', {
                                                stateOverride: {
                                                    filter: 'SYNCED', // "Paid" orders
                                                    selectedPreset: deliveryPreset,
                                                }
                                            });
                                            console.log("🚀 Navigating to TicketScreen via this.navigate (Odoo 19)");
                                        } else {
                                            console.error("❌ navigate/showScreen not found on PosStore");
                                        }
                                    },
                                    primary: true,
                                }
                            ],
                        }
                    );
                    console.log("🔔 Toast notification sent to service for order", orderId);
                } catch (notifErr) {
                    console.error("❌ Notification service failed:", notifErr);
                }
            }

            // === 3. LOAD & PRINT THE ORDER ===
            let order = this.models["pos.order"].get(orderId);
            
            if (!order) {
                // If not found locally, load it from the server
                await this.data.loadServerOrders([["id", "=", orderId]]);
                order = this.models["pos.order"].get(orderId);
            }
            
            if (order && this.config.accept_remote_orders) {
                // Only attempt print if it's a new 'received' order
                if (order.delivery_status === 'received' && !order.is_remote_printed) {
                    // Use standard POS Data service (this.data.call)
                    const shouldPrint = await this.data.call(
                         "pos.order", 
                         "claim_remote_print", 
                         [order.id, this.session.id]
                    );

                    if (shouldPrint) {
                         console.log("🖨️ Printing Remote Order Ticket:", order.name);
                         order.is_remote_printed = true;
                         
                         // If kitchen printers are configured, trigger the print
                         if (this.printer && this.config.iface_printer_id) {
                              // await order.printChanges(); 
                         }
                    }
                }
            }
        } catch (e) {
             console.error("❌ Remote Order Processing Failed:", e);
        }
    }
});
