/** @odoo-module */

import { Component, proxy, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { patch } from "@web/core/utils/patch";

export class DeliveryToggle extends Component {
    static template = "pos_order_api.DeliveryToggle";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.bus = useService("bus_service");
        
        // Use pos.config for persistence state
        const isDeliveryActive = Boolean(this.pos?.config?.accept_remote_orders);
        this.state = proxy({ 
            isActive: isDeliveryActive
        });

        // Listen for backend updates via Bus
        if (this.pos?.config?.id && this.bus) {
            this.bus.addChannel(`pos_config_${this.pos.config.id}`);
            this.bus.subscribe("POS_CONFIG_UPDATE", (data) => {
                if (data.accept_remote_orders !== undefined) {
                    this.state.isActive = Boolean(data.accept_remote_orders);
                    if (this.pos.config) {
                        this.pos.config.accept_remote_orders = data.accept_remote_orders;
                    }
                }
            });
        }
    }

    async toggleDelivery() {
        const newState = !this.state.isActive;
        try {
            // Updated to use the generic pos.config write or specialized action
            // Reusing action_toggle_delivery but ensuring it updates config
            await this.orm.call("pos.session", "action_toggle_delivery", [
                this.pos.session.id, 
                newState
            ]);
            // The bus notification will eventually update the state, 
            // but we update locally for immediate feedback
            this.state.isActive = newState;
            if (this.pos.config) {
                this.pos.config.accept_remote_orders = newState;
            }
        } catch (e) {
            console.error("Failed to toggle delivery:", e);
        }
    }
}

// Register the component so Navbar can use it
Navbar.components = { ...Navbar.components, DeliveryToggle };
