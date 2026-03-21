/** @odoo-module */

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

export class DeliveryStatusPanel extends Component {
    static template = "pos_order_api.DeliveryStatusPanel";
    static props = {
        order: { type: Object },
    };

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
    }

    get statusLabel() {
        const statusMap = {
            received: "Received",
            preparing: "Preparing",
            ready: "Ready",
            on_the_way: "On the Way",
            delivered: "Delivered",
            cancelled: "Cancelled",
        };
        return statusMap[this.props.order.delivery_status] || this.props.order.delivery_status;
    }

    get nextStatus() {
        const flow = {
            received: 'preparing',
            preparing: 'ready',
            ready: 'on_the_way',
            on_the_way: 'delivered',
        };
        return flow[this.props.order.delivery_status];
    }

    get nextStatusLabel() {
        const statusMap = {
            preparing: "Start Preparing",
            ready: "Mark Ready",
            on_the_way: "Sent for Delivery",
            delivered: "Mark Delivered",
        };
        return statusMap[this.nextStatus];
    }

    async updateStatus(newStatus) {
        try {
            await this.orm.call("pos.order", "update_delivery_status", [
                this.props.order.id,
                newStatus
            ]);
            // Local update for immediate feedback (though bus will also trigger it)
            this.props.order.delivery_status = newStatus;
        } catch (e) {
            console.error("Failed to update delivery status:", e);
        }
    }
}

// Register the component for use in the TicketScreen
patch(TicketScreen, {
    components: { ...TicketScreen.components, DeliveryStatusPanel }
});
