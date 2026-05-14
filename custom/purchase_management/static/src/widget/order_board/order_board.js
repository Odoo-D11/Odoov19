/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class PurchaseOrderBoardWidget extends Component {
    static template = "purchase_management.PurchaseOrderBoardWidget";
    static supportedTypes = ["one2many"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: false,
            totalItems: 0,
            totalPrice: 0,
            currencyName: "",
        });

        this._lastRequestQuotationId = null;
        this._lastResId = null;
        this._cachedAddViewId = undefined;

        onWillStart(async () => {
            try {
                await this._loadData(this.props);
            } catch (error) {
                console.error("Error inicializando OrderBoard:", error);
                this.state.loading = false;
            }
        });

        onWillUpdateProps(async (nextProps) => {
            try {
                const nextResId = nextProps.record.resId || null;
                const nextReqId = nextProps.record.data.request_quotation_id?.id || null;
                if (nextResId !== this._lastResId || nextReqId !== this._lastRequestQuotationId) {
                    await this._loadData(nextProps);
                }
            } catch (error) {
                console.error("Error actualizando OrderBoard:", error);
                this.state.loading = false;
            }
        });
    }

    async _loadData(props = this.props, { silent = false } = {}) {
        const requestQuotationId = props.record.data.request_quotation_id?.id || null;
        this._lastRequestQuotationId = requestQuotationId;
        this._lastResId = props.record.resId || null;

        if (!requestQuotationId) {
            this.state.totalItems = 0;
            this.state.totalPrice = 0;
            return;
        }

        if (!silent) this.state.loading = true;
        try {
            // Contar y sumar las líneas reales de la OC en la moneda de la OC
            const resId = props.record.resId;
            let newItems = 0;
            let newPrice = 0;
            if (resId) {
                const orderLines = await this.orm.searchRead(
                    "purchase.management.order.line",
                    [["order_id", "=", resId]],
                    ["subtotal", "currency_id"]
                );
                newItems = orderLines.length;
                newPrice = orderLines.reduce((acc, l) => acc + (l.subtotal || 0), 0);
                const lineCurrency = orderLines[0]?.currency_id;
                const newCurrencyName = Array.isArray(lineCurrency) ? lineCurrency[1] : "";
                if (newCurrencyName !== this.state.currencyName) this.state.currencyName = newCurrencyName;
            }

            if (newItems !== this.state.totalItems) this.state.totalItems = newItems;
            if (newPrice !== this.state.totalPrice) this.state.totalPrice = newPrice;
        } catch (err) {
            console.error("OrderBoard: error cargando datos", err);
        } finally {
            if (!silent) this.state.loading = false;
        }
    }

    // ── Getters ──────────────────────────────────────────────────────────

    get hasData() {
        return !this.state.loading && this.state.totalItems > 0;
    }

    get itemLabel() {
        const typeId = this.props.record.data.type_id;
        const typeName = typeId?.display_name || "";
        if (typeName.includes("Servicio")) return this.state.totalItems === 1 ? "Servicio" : "Servicios";
        if (typeName.includes("Mixto")) return this.state.totalItems === 1 ? "Ítem" : "Ítems";
        return this.state.totalItems === 1 ? "Producto" : "Productos";
    }

    get widgetTitle() {
        const typeId = this.props.record.data.type_id;
        const typeName = typeId?.display_name || "";
        if (typeName.includes("Servicio")) return "Servicios";
        if (typeName.includes("Mixto")) return "Elementos";
        return "Productos";
    }

    get emptyTitle() {
        const typeId = this.props.record.data.type_id;
        const typeName = typeId?.display_name || "";
        if (typeName.includes("Servicio")) return "Sin servicios registrados";
        if (typeName.includes("Mixto")) return "Sin elementos registrados";
        return "Sin productos registrados";
    }

    get emptyDescription() {
        return "Esta orden no tiene líneas aún. Vincula una solicitud de cotización aprobada para ver el resumen aquí.";
    }

    get currencyName() {
        return this.state.currencyName;
    }

    get isForeignCurrency() {
        return (this.props.record.data.trm || 0) > 0;
    }

    // ── Formato ──────────────────────────────────────────────────────────

    formatPrice(amount) {
        const decimals = this.isForeignCurrency ? 2 : 0;
        return new Intl.NumberFormat("es-CO", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(amount);
    }

    // ── Acciones ─────────────────────────────────────────────────────────

    async _getAddViewId() {
        if (this._cachedAddViewId !== undefined) return this._cachedAddViewId;
        try {
            const viewId = await this.orm.call(
                "purchase.management.order",
                "get_add_product_form_view_id",
                [],
                {}
            );
            this._cachedAddViewId = viewId || false;
        } catch {
            this._cachedAddViewId = false;
        }
        return this._cachedAddViewId;
    }

    async openOrderLines() {
        const recordId = this.props.record.resId;
        if (!recordId) {
            this.notification.add(
                "Primero guarda la orden de compra para gestionar las líneas.",
                { type: "warning" }
            );
            return;
        }
        try {
            const viewId = await this._getAddViewId();
            await this.actionService.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: "purchase.management.order",
                    res_id: recordId,
                    view_mode: "form",
                    views: [[viewId || false, "form"]],
                    target: "new",
                    name: "Odoo",
                },
                { onClose: () => this._loadData(this.props, { silent: true }) }
            );
        } catch (err) {
            console.error("OrderBoard: error abriendo líneas", err);
            this.notification.add("No se pudieron abrir las líneas de la orden.", { type: "danger" });
        }
    }

}

registry.category("fields").add("OrderBoard", {
    component: PurchaseOrderBoardWidget,
    displayName: "Widget de Orden de Compra",
    supportedTypes: PurchaseOrderBoardWidget.supportedTypes,
});
