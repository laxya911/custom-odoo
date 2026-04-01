/** @odoo-module */
import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { PartnerList } from "@point_of_sale/app/screens/partner_list/partner_list";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { useService } from "@web/core/utils/hooks";

export class BookingCreationPopup extends Component {
    static template = "table_booking_pos.BookingCreationPopup";
    static components = { Dialog };
    static props = {
        partner: { type: [{ value: null }, Object], optional: true },
        getPayload: { type: Function, optional: true },
        close: { type: Function },
        confirm: { type: Function, optional: true },
    };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
        
        const now = new Date();
        const tomorrow = new Date(now);
        tomorrow.setHours(now.getHours() + 1);
        
        this.state = useState({
            customerName: this.props.partner?.name || "",
            customerPhone: this.props.partner?.phone || "",
            customerEmail: this.props.partner?.email || "",
            date: now.toISOString().split("T")[0],
            time: `${String(tomorrow.getHours()).padStart(2, '0')}:00`,
            partySize: 2,
            notes: "",
            tableIds: [],
            availableResources: [],
            configId: null,
            isLoading: true,
            error: null,
        });

        onWillStart(async () => {
            await this.loadConfigAndResources();
        });
    }

    async loadConfigAndResources() {
        try {
            // 1. Find config linked to this POS
            const configs = await this.pos.data.call(
                "table.booking.config",
                "search_read",
                [[["pos_config_id", "=", this.pos.config.id], ["active_booking", "=", true]]],
                { fields: ["id", "max_party_size"] }
            );

            if (configs.length > 0) {
                this.state.configId = configs[0].id;
            } else {
                // Fallback: any active config
                const anyConfig = await this.pos.data.call(
                    "table.booking.config",
                    "search_read",
                    [[["active_booking", "=", true]]],
                    { fields: ["id"], limit: 1 }
                );
                if (anyConfig.length > 0) this.state.configId = anyConfig[0].id;
            }

            // 2. Load tables/resources
            const resources = await this.pos.data.call(
                "table.resource",
                "search_read",
                [[["active", "=", true]]],
                { fields: ["id", "name", "capacity"] }
            );
            this.state.availableResources = resources;
        } catch (e) {
            console.error("BookingPopup: Error loading metadata", e);
            this.state.error = _t("Failed to load booking configuration.");
        } finally {
            this.state.isLoading = false;
        }
    }

    async confirm() {
        if (!this.state.configId) {
            this.state.error = _t("No active booking configuration found.");
            return;
        }
        if (!this.state.customerName || !this.state.customerPhone) {
            this.state.error = _t("Customer name and phone are required.");
            return;
        }
        if (this.state.tableIds.length === 0) {
            this.state.error = _t("Please select at least one table.");
            return;
        }

        try {
            this.state.isLoading = true;
            this.state.error = null;
            
            // 0. Capacity Check
            const selectedCapacity = this.state.tableIds.reduce((total, id) => {
                const table = this.state.availableResources.find(t => t.id === id);
                return total + (table?.capacity || 0);
            }, 0);

            if (selectedCapacity < this.state.partySize) {
                this.state.error = _t("Insufficient capacity. Selected tables only hold %s people.", selectedCapacity);
                return;
            }

            const startDateTime = `${this.state.date} ${this.state.time}:00`;
            // Calculate end time (start + 90 minutes) using standard JS
            const startDate = new Date(startDateTime.replace(' ', 'T'));
            const endDate = new Date(startDate.getTime() + 90 * 60000);
            
            // Format to YYYY-MM-DD HH:mm:ss for backend
            const endStr = endDate.getFullYear() + '-' + 
                String(endDate.getMonth() + 1).padStart(2, '0') + '-' + 
                String(endDate.getDate()).padStart(2, '0') + ' ' + 
                String(endDate.getHours()).padStart(2, '0') + ':' + 
                String(endDate.getMinutes()).padStart(2, '0') + ':' + 
                String(endDate.getSeconds()).padStart(2, '0');

            const payload = {
                config_id: this.state.configId,
                party_size: this.state.partySize,
                customer: {
                    name: this.state.customerName,
                    phone: this.state.customerPhone,
                    email: this.state.customerEmail,
                    notes: this.state.notes,
                },
                slot: {
                    start_time: startDateTime,
                    end_time: endStr,
                    tables: this.state.tableIds.map(id => ({ id })),
                }
            };

            const result = await this.pos.data.call("table.booking", "create_booking", [], payload);
            
            if (result.status === 'success') {
                if (this.props.confirm) this.props.confirm();
                if (this.props.getPayload) this.props.getPayload(result);
                this.props.close();
            } else {
                this.state.error = result.message || _t("Failed to create booking.");
            }
        } catch (e) {
            this.state.error = e.message || _t("An error occurred during booking creation.");
        } finally {
            this.state.isLoading = false;
        }
    }

    toggleTable(tableId) {
        if (this.state.tableIds.includes(tableId)) {
            this.state.tableIds = this.state.tableIds.filter(id => id !== tableId);
        } else {
            this.state.tableIds.push(tableId);
        }
    }

    async selectPartner() {
        const partner = await makeAwaitable(this.dialog, PartnerList, {
            partner: null,
        });
        if (partner) {
            this.state.customerName = partner.name || "";
            this.state.customerPhone = partner.phone || "";
            this.state.customerEmail = partner.email || "";
        }
    }
}
