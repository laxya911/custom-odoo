/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { onWillUnmount, onWillUpdateProps } from "@odoo/owl";

// Patch TicketScreen so it responds live to incoming orders and state navigation
patch(TicketScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos.ticketScreenInstance = this;

        onWillUnmount(() => {
            if (this.pos.ticketScreenInstance === this) {
                this.pos.ticketScreenInstance = null;
            }
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps?.stateOverride) {
                await this.applyStateOverride(nextProps.stateOverride);
            }
        });
    },

    async applyStateOverride(override) {
        if (!override) return;
        Object.assign(this.state, override);
        if (override.filter) {
            this.pos.screenState.ticketScreen.totalCount = 0;
            this.pos.screenState.ticketScreen.offsetByDomain = {};
            await this.onFilterSelected(override.filter);
        }
        if (override.selectedOrderUuid) {
            this.state.selectedOrderUuid = override.selectedOrderUuid;
        }
    },

    getFilteredOrderList() {
        const orderModel = this.pos.models["pos.order"];
        // When viewing Active Orders, also list online/remote orders that haven't been delivered
        if (!this.state.filter || this.state.filter === "ACTIVE_ORDERS") {
            const activeOrders = orderModel.filter(
                (o) =>
                    (!this.isOrderDoneOrPaid(o) && !this.isOrderCancelled(o)) ||
                    o.getScreenData().name === "TipScreen" ||
                    (o.is_api_order && o.delivery_status && !['delivered', 'cancel'].includes(o.delivery_status))
            );
            return activeOrders;
        }
        return super.getFilteredOrderList();
    },
});

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
                this.data.connectWebSocket("NEW_REMOTE_ORDER", (payload) => {
                    this._onNewRemoteOrder(payload);
                });
                console.log("POS Remote Print: Listening for NEW_REMOTE_ORDER via connectWebSocket");
            }
        } catch (err) {
            console.error("remote_print: Failed to initialize remote order listener:", err);
        }
    },

    async openOrderInTicketScreen(orderId, payload = {}) {
        console.log("🚀 openOrderInTicketScreen for order:", orderId, payload);
        try {
            // 1. Ensure order is loaded in POS memory
            let order = this.models["pos.order"].get(orderId);
            if (!order) {
                console.log("📥 Loading remote order from backend:", orderId);
                const loaded = await this.data.loadServerOrders([["id", "=", orderId]]);
                order = loaded?.[0] || this.models["pos.order"].get(orderId);
            }

            const targetUuid = order?.uuid || payload?.uuid;

            // 2. Clear pagination cache so latest synced orders are fetched
            if (this.screenState && this.screenState.ticketScreen) {
                this.screenState.ticketScreen.offsetByDomain = {};
                this.screenState.ticketScreen.totalCount = 0;
            }

            // 3. Prepare state override for TicketScreen
            const stateOverride = {
                filter: "SYNCED",
                selectedOrderUuid: targetUuid,
                selectedPreset: null,
            };

            // 4. If TicketScreen is already open, update it live
            if (this.ticketScreenInstance) {
                await this.ticketScreenInstance.applyStateOverride(stateOverride);
            }

            // 5. Navigate to TicketScreen
            this.navigate("TicketScreen", { stateOverride });
            console.log("✅ Navigated to TicketScreen with target:", targetUuid);
        } catch (err) {
            console.error("❌ Failed to open order in TicketScreen:", err);
        }
    },

    async _onNewRemoteOrder(payload) {
        console.log("🚀 Remote Order Signal received:", payload);
        
        try {
            const orderId = payload.order_id;
            
            // Deduplicate
            if (this._processedRemoteOrders && this._processedRemoteOrders.has(orderId)) {
                console.log(`⏭️ Order ${orderId} already processed, skipping duplicate`);
                return;
            }
            if (this._processedRemoteOrders) {
                this._processedRemoteOrders.add(orderId);
                setTimeout(() => this._processedRemoteOrders?.delete(orderId), 60000);
            }

            // 1. Play Notification Sound
            try {
                if (this.sound && typeof this.sound.play === 'function') {
                    this.sound.play("order-receive-tone");
                    console.log("🔔 Sound 'order-receive-tone' played via PosStore");
                } else {
                    const audio = new Audio("/point_of_sale/static/src/sounds/notification");
                    audio.volume = 1.0;
                    audio.play().catch(e => console.warn("🔔 Fallback audio play failed:", e));
                }
            } catch (soundErr) {
                console.warn("🔔 Sound play failed:", soundErr.message);
            }

            // 2. Pre-load the order into POS local memory
            let order = this.models["pos.order"].get(orderId);
            if (!order) {
                try {
                    const loaded = await this.data.loadServerOrders([["id", "=", orderId]]);
                    order = loaded?.[0] || this.models["pos.order"].get(orderId);
                } catch (loadErr) {
                    console.warn("⚠️ Error preloading remote order:", loadErr);
                }
            }

            // 3. If TicketScreen is currently mounted, live refresh the list
            if (this.ticketScreenInstance) {
                try {
                    this.screenState.ticketScreen.totalCount = 0;
                    this.screenState.ticketScreen.offsetByDomain = {};
                    this.ticketScreenInstance.onFilterSelected(this.ticketScreenInstance.state.filter);
                } catch (tsErr) {
                    console.warn("⚠️ Live refresh on TicketScreen failed:", tsErr);
                }
            }

            // 4. Show Toast Notification with working "View Order" button
            if (this.notification) {
                try {
                    let closeNotif = null;
                    closeNotif = this.notification.add(
                        `New Online Order: ${payload.pos_reference || '#' + orderId}`,
                        {
                            title: "🔔 New Order Received!",
                            type: "success",
                            sticky: true,
                            buttons: [
                                {
                                    name: "View Order",
                                    onClick: async () => {
                                        console.log("🚀 Notification button clicked for order:", orderId);
                                        if (typeof closeNotif === "function") {
                                            closeNotif();
                                        }
                                        await this.openOrderInTicketScreen(orderId, payload);
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

            // 5. Kitchen Print Claim if configured
            if (order && this.config.accept_remote_orders) {
                if (order.delivery_status === 'received' && !order.is_remote_printed) {
                    const shouldPrint = await this.data.call(
                         "pos.order", 
                         "claim_remote_print", 
                         [order.id, this.session.id]
                    );

                    if (shouldPrint) {
                         console.log("🖨️ Printing Remote Order Ticket:", order.name);
                         order.is_remote_printed = true;
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
