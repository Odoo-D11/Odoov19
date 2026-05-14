/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount, onWillUpdateProps, onMounted, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registerWidget, toggleActiveWidget, setDefaultWidget } from "../shared/board_switcher";

const PRODUCT_NOTIFICATION_TYPE = "purchase_management.product/update";

class RequestQuotationProductBoardWidget extends Component {
    static template = "purchase_management.RequestQuotationProductBoardWidget";
    static supportedTypes = ["one2many"];

    setup() {
        super.setup();
        this.isDestroyed = false;
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.busService = useService("bus_service");
        this.boardCache = useService("purchase_management.board_cache");

        if (!this.props.record) {
            console.warn("ProductBoard: No record found in props");
            this.state = useState({ products: [], loading: false, isVisible: false, lastUpdateHash: "" });
            return;
        }

        this.requestQuotationId = this.props.record.resId || this.props.record._config?.resId || false;
        this.modelName = this.props.record.resModel || "request.quotation";

        this.state = useState({
            products: [],
            loading: this.hasProducts(),
            isVisible: false,
            lastUpdateHash: "",
        });

        const recordData = this.props.record.data || {};
        const recordState = recordData.state || "draft";
        const allQuotationRejected = recordData.all_quotation_rejected || false;
        const commiteeApprovalRejected = recordData.commitee_approval_rejected || false;

        setDefaultWidget(recordState, this.requestQuotationId, {
            allQuotationRejected,
            commiteeApprovalRejected
        });

        this.unregisterVisibility = registerWidget("product", (isVisible) => {
            if (this.state) {
                this.state.isVisible = isVisible;
            }
        });

        this.productLineKey = JSON.stringify(recordData.product_line_ids?.resIds || []);
        this.productFallbackTimer = null;
        this.productFallbackDelay = 15000;
        this.maxProductPollingDelay = 120000;
        this.activeProductChannel = null;
        this.productNotificationHandler = this.handleProductNotification.bind(this);
        this.onBusConnect = () => {
            this.stopProductFallbackPolling();
        };
        this.onBusReconnect = () => {
            this.stopProductFallbackPolling();
            this.activeProductChannel = null;
            this.ensureProductChannel(this.requestQuotationId);
        };
        this.onBusDisconnect = () => {
            this.activeProductChannel = null;
            this.startProductFallbackPolling();
        };
        this.busEventHandlers = {
            connect: this.onBusConnect,
            reconnect: this.onBusReconnect,
            disconnect: this.onBusDisconnect,
        };
        this.loadVersion = 0;
        this._lastFetchTimestamp = 0;

        this.busService.subscribe(
            PRODUCT_NOTIFICATION_TYPE,
            this.productNotificationHandler
        );
        for (const [event, handler] of Object.entries(this.busEventHandlers)) {
            this.busService.addEventListener(event, handler);
        }

        this._onVisibilityChange = () => {
            if (document.hidden) {
                this.stopProductFallbackPolling();
            } else if (!this.busService.isActive) {
                this.productFallbackDelay = 15000;
                this.startProductFallbackPolling();
            }
        };
        document.addEventListener('visibilitychange', this._onVisibilityChange);

        onWillStart(async () => {
            try {
                this.state.loading = this.hasProducts();
                await this.fetchProductsFromBoard(this.requestQuotationId, { resetHash: true });
            } catch (error) {
                console.error("Error inicializando ProductBoard:", error);
                this.state.loading = false;
            }
        });

        onMounted(async () => {
            try {
                await this.ensureProductChannel(this.requestQuotationId);
            } catch (error) {
                console.error("Error suscribiéndose al canal de productos en mount:", error);
            }
            if (!this.busService.isActive) {
                this.startProductFallbackPolling();
            }
        });

        onWillUpdateProps(async (nextProps) => {
            try {
                const nextRecordState = nextProps.record.data.state;
                const nextRecordId = nextProps.record.resId || false;

                const nextAllQuotationRejected = nextProps.record.data.all_quotation_rejected;
                const nextCommiteeApprovalRejected = nextProps.record.data.commitee_approval_rejected;

                setDefaultWidget(nextRecordState, nextRecordId, {
                    allQuotationRejected: nextAllQuotationRejected,
                    commiteeApprovalRejected: nextCommiteeApprovalRejected
                });

                const newKey = JSON.stringify(
                    nextProps.record.data.product_line_ids?.resIds || []
                );
                const newrequestQuotationId = nextProps.record.resId;

                if (newKey !== this.productLineKey || newrequestQuotationId !== this.requestQuotationId) {
                    const now = Date.now();
                    if (now - this._lastFetchTimestamp < 500) {
                        this.productLineKey = newKey;
                        this.requestQuotationId = newrequestQuotationId;
                        return;
                    }
                    this._lastFetchTimestamp = now;
                    this.productLineKey = newKey;
                    this.requestQuotationId = newrequestQuotationId;

                    this.state.products = [];
                    this.state.loading = this.hasProducts(nextProps);
                    this.state.lastUpdateHash = "";

                    await this.fetchProducts(newrequestQuotationId, { props: nextProps, resetHash: true });
                    await this.ensureProductChannel(newrequestQuotationId);
                }
            } catch (error) {
                console.error("Error actualizando ProductBoard:", error);
                try { this.state.loading = false; } catch (e) { /* componente destruido */ }
            }
        });

        onWillUnmount(() => {
            this.isDestroyed = true;
            this.unregisterVisibility?.();
            this.stopProductFallbackPolling();
            this.busService.unsubscribe(
                PRODUCT_NOTIFICATION_TYPE,
                this.productNotificationHandler
            );
            for (const [event, handler] of Object.entries(this.busEventHandlers)) {
                this.busService.removeEventListener(event, handler);
            }
            this.disconnectProductChannel();
            document.removeEventListener('visibilitychange', this._onVisibilityChange);
        });
    }

    _isComponentDestroyedError(error) {
        return error?.message?.includes('Component is destroyed');
    }

    async fetchProductsFromBoard(requestQuotationId, { resetHash = false, props = this.props } = {}) {
        const loadVersion = ++this.loadVersion;
        if (this.isDestroyed) return;
        this.state.loading = this.hasProducts(props);

        if (resetHash) {
            this.state.lastUpdateHash = "";
        }

        if (!requestQuotationId) {
            if (this.isDestroyed) return;
            Object.assign(this.state, { products: [], loading: false });
            return;
        }

        try {
            const boardData = await this.boardCache.getBoardData(requestQuotationId, this.modelName);

            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            if (requestQuotationId !== (this.props.record.resId || this.props.record._config?.resId)) return;

            const products = boardData.products || [];
            const nextHash = this.getProductUpdateHash(products);
            if (!resetHash && nextHash === this.state.lastUpdateHash) return;

            this.state.products = products;
            this.state.lastUpdateHash = nextHash;
        } catch (error) {
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            if (this._isComponentDestroyedError(error)) return;
            console.warn("Error al cargar los productos desde board data", error);
            await this.fetchProducts(requestQuotationId, { props, resetHash });
        } finally {
            try {
                if (!this.isDestroyed && loadVersion === this.loadVersion) {
                    this.state.loading = false;
                }
            } catch (e) { /* componente destruido */ }
        }
    }

    async fetchProductUpdates() {
        const requestQuotationId = this.props.record.resId;
        if (!requestQuotationId || this.isDestroyed) {
            return;
        }

        try {
            const result = await this.orm.call(
                this.modelName,
                "get_board_update_hash",
                [requestQuotationId]
            );
            if (this.isDestroyed || requestQuotationId !== this.props.record.resId) return;

            const serverHash = result.hash || '';
            if (serverHash && serverHash !== this.state.lastUpdateHash) {
                this.state.lastUpdateHash = serverHash;
                await this.fetchProducts(requestQuotationId);
            }
        } catch (error) {
            console.error("Error checking for product updates:", error);
        }
    }

    async fetchProducts(
        requestQuotationId = this.props.record.resId,
        { props = this.props, resetHash = false } = {}
    ) {
        const loadVersion = ++this.loadVersion;
        if (this.isDestroyed) return;
        this.state.loading = this.hasProducts(props);

        if (resetHash) {
            this.state.lastUpdateHash = "";
        }

        if (!requestQuotationId) {
            if (this.isDestroyed) return;
            Object.assign(this.state, { products: [], loading: false });
            return;
        }

        try {
            const products = await this.orm.searchRead(
                "request.product.quotation.line",
                [["request_quotation_id", "=", requestQuotationId]],
                [
                    "id",
                    "qty",
                    "display_type",
                ]
            );

            if (this.isDestroyed || loadVersion !== this.loadVersion) {
                return;
            }
            if (requestQuotationId !== this.props.record.resId) {
                return;
            }

            const nextHash = this.getProductUpdateHash(products);
            if (!resetHash && nextHash === this.state.lastUpdateHash) {
                return;
            }

            this.state.products = products;
            this.state.lastUpdateHash = nextHash;
        } catch (error) {
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            if (this._isComponentDestroyedError(error)) return;
            console.error("Error al cargar los productos de la cotización", error);
            this.notification.add(
                _t("No se pudieron cargar los productos. Intenta nuevamente."),
                { type: "danger" }
            );
        } finally {
            try {
                if (!this.isDestroyed && loadVersion === this.loadVersion) {
                    this.state.loading = false;
                }
            } catch (e) { /* componente destruido */ }
        }
    }

    async handleProductNotification(payload) {
        const requestQuotationId = this.props.record.resId;
        if (
            !payload ||
            !requestQuotationId ||
            payload.request_quotation_id !== requestQuotationId
        ) {
            return;
        }
        await this.fetchProducts(requestQuotationId);
    }

    getProductChannel(requestQuotationId) {
        return `request_quotation_products${requestQuotationId}`;
    }

    async ensureProductChannel(requestQuotationId) {
        const expectedChannel = requestQuotationId ? this.getProductChannel(requestQuotationId) : null;

        if (this.activeProductChannel === expectedChannel) {
            return;
        }

        this.disconnectProductChannel();

        if (!expectedChannel) {
            this.stopProductFallbackPolling();
            return;
        }

        try {
            await this.busService.addChannel(expectedChannel);
            this.activeProductChannel = expectedChannel;
            this.stopProductFallbackPolling();
        } catch (error) {
            console.error('Error suscribiéndose al canal de productos:', error);
            this.startProductFallbackPolling();
        }
    }

    getProductUpdateHash(products) {
        return JSON.stringify({
            productCount: products.length,
            quantities: products.map((product) => ({
                id: product.id,
                qty: product.qty || 0,
            })),
        });
    }

    disconnectProductChannel() {
        if (this.activeProductChannel) {
            this.busService.deleteChannel(this.activeProductChannel);
            this.activeProductChannel = null;
        }
    }

    startProductFallbackPolling() {
        if (this.productFallbackTimer) return;

        const requestQuotationId = this.props.record.resId;
        if (!requestQuotationId) return;

        const poll = async () => {
            if (document.hidden) return;
            const prevHash = this.state.lastUpdateHash;
            await this.fetchProductUpdates();
            if (this.state.lastUpdateHash !== prevHash) {
                this.productFallbackDelay = 15000;
            } else {
                this.productFallbackDelay = Math.min(this.productFallbackDelay * 1.5, this.maxProductPollingDelay);
            }
            if (this.productFallbackTimer) {
                clearInterval(this.productFallbackTimer);
                this.productFallbackTimer = setInterval(poll, this.productFallbackDelay);
            }
        };
        poll();
        this.productFallbackTimer = setInterval(poll, this.productFallbackDelay);
    }

    stopProductFallbackPolling() {
        if (this.productFallbackTimer) {
            clearInterval(this.productFallbackTimer);
            this.productFallbackTimer = null;
        }
    }

    get showAddButton() {
        return this.state.products.length === 0;
    }

    get showBulkUploadButton() {
        const state = this.props.record.data.state;
        return !state || state === 'draft';
    }

    get showToggleButton() {
        const state = this.props.record.data.state;
        const allQuotationRejected = this.props.record.data.all_quotation_rejected;
        const commiteeApprovalRejected = this.props.record.data.commitee_approval_rejected;

        if (allQuotationRejected || commiteeApprovalRejected) {
            return false;
        }

        return !['draft'].includes(state);
    }

    hasProducts(props = this.props) {
        return (props.record?.data?.product_line_ids?.resIds || []).length > 0;
    }

    getTotalQuantity() {
        return this.state.products
            .filter(product => product.display_type !== 'line_note')
            .length;
    }

    getUnitsText() {
        const totalQuantity = this.getTotalQuantity();
        if (totalQuantity === 1) {
            return "Producto Solicitado";
        }
        return "Productos Solicitados";
    }

    getEstimatedPriceText() {
        return "Precio Estimado";
    }

    getTopProductsText() {
        if (!this.state.products.length) return '';

        const topProducts = this.state.products.slice(0, 3);
        const productNames = topProducts.map(p => p.product_id[1]).join(', ');

        if (this.state.products.length > 3) {
            return `${productNames}...`;
        }
        return productNames;
    }

    getUniqueUoMsText() {
        if (!this.state.products.length) return '';

        const uniqueUoMs = [...new Set(
            this.state.products
                .filter(p => p.uom_id && p.uom_id[1])
                .map(p => p.uom_id[1])
        )];

        return uniqueUoMs.slice(0, 2).join(', ') + (uniqueUoMs.length > 2 ? '...' : '');
    }

    async deleteAllProducts() {
        const requestQuotationId = this.props.record.resId;
        const state = this.props.record.data.state;

        if (state !== 'draft') {
            this.notification.add(
                _t("No se pueden eliminar productos de una solicitud de cotización que no está en estado Borrador."),
                { type: "danger" }
            );
            return;
        }

        this.dialog.add(ConfirmationDialog, {
            body: "¿Está seguro de que desea eliminar todos los productos de esta solicitud de cotización?",
            confirm: async () => {
                try {
                    const productIds = this.state.products.map(p => p.id);
                    await this.orm.unlink("request.product.quotation.line", productIds);

                    await this.fetchProducts();
                    this.notification.add(
                        "Productos eliminados correctamente",
                        { type: "success" }
                    );
                } catch (error) {
                    this.notification.add(
                        "Error al eliminar los productos",
                        { type: "danger" }
                    );
                    console.error('Error deleting products:', error);
                }
            },
            cancel: () => { },
        });
    }

    onToggleWidget() {
        toggleActiveWidget();
    }

    async getProductWizardViewId() {
        if (this._cachedWizardViewId !== undefined) {
            return this._cachedWizardViewId;
        }
        const data = await this.orm.call(
            this.modelName,
            'get_product_wizard_view_id',
            [],
            {}
        );
        this._cachedWizardViewId = data;
        return data;
    }

    async openProductManager() {
        const requestQuotationId = this.props.record.resId;
        if (!requestQuotationId) {
            this.notification.add(
                _t("Error: No se puede abrir la gestión de productos sin una solicitud de cotización guardada."),
                { type: "danger" }
            );
            return;
        }

        try {
            const viewId = await this.getProductWizardViewId();
            if (!viewId) {
                this.notification.add(
                    _t("No se encontró la vista específica para gestionar los productos. Se utilizará la vista predeterminada."),
                    { type: "warning" }
                );
            }

            const refreshProducts = async () => setTimeout(() => this.fetchProducts(), 200);
            const dialog = await this.actionService.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: this.modelName,
                    view_mode: "form",
                    views: [[viewId || false, "form"]],
                    view_id: viewId || false,
                    target: "new",
                    res_id: requestQuotationId,
                    name: "Odoo",
                },
                { onClose: refreshProducts }
            );

            if (dialog && dialog.on_close) {
                dialog.on_close(refreshProducts);
            }
        } catch (error) {
            console.error("Error opening product manager dialog", error);
            this.notification.add(
                _t("No se pudo abrir la gestión de productos. Intenta nuevamente."),
                { type: "danger" }
            );
        }
    }

    async addProductLine() {
        const requestQuotationId = this.props.record.resId;
        const typeId = this.props.record.data.type_id;
        const state = this.props.record.data.state;
        if (!requestQuotationId) {
            const typeName = (typeId && typeId.display_name) || '';
            let itemType = 'productos';

            if (typeName.includes("Servicios")) {
                itemType = 'servicios';
            } else if (typeName.includes("Mixtos")) {
                itemType = 'ítems';
            }
            this.notification.add(
                _t(`Para agregar ${itemType}, primero debes guardar la solicitud de cotización. Por favor, verifica e intenta nuevamente.`),
                { type: "danger" }
            );
            return;
        }
        if (state !== 'draft') {
            this.notification.add(
                _t("No se pueden agregar productos a una solicitud de cotización que no está en estado Borrador. Por favor, verifica e intenta nuevamente."),
                { type: "danger" }
            );
            return;
        }
        if (!typeId || !typeId.id) {
            this.notification.add(
                _t("Para agregar productos, primero debes seleccionar el tipo de solicitud. Por favor, verifica e intenta nuevamente."),
                { type: "danger" }
            );
            return;
        }

        try {
            const viewId = await this.getProductWizardViewId();
            if (!viewId) {
                this.notification.add(
                    _t("No se encontró la vista específica para gestionar los productos. Se utilizará la vista predeterminada."),
                    { type: "warning" }
                );
            }

            const refreshProducts = async () => setTimeout(() => this.fetchProducts(), 200);
            const dialog = await this.actionService.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: this.modelName,
                    view_mode: "form",
                    views: [[viewId || false, "form"]],
                    view_id: viewId || false,
                    target: "new",
                    res_id: requestQuotationId,
                    name: "Odoo",
                },
                { onClose: refreshProducts }
            );

            if (dialog && dialog.on_close) {
                dialog.on_close(refreshProducts);
            }
        } catch (error) {
            console.error("Error abriendo el asistente de gestión de productos", error);
            this.notification.add(
                _t("No se pudo abrir la gestión de productos. Intenta nuevamente."),
                { type: "danger" }
            );
        }
    }

    async openBulkUploadWizard() {
        const requestQuotationId = this.props.record.resId;
        if (!requestQuotationId) {
            this.notification.add(
                _t("Para realizar un cargue masivo desde Excel, primero debes guardar la solicitud de cotización. Por favor, verifica e intenta nuevamente."),
                { type: 'danger' }
            );
            return;
        }

        const state = this.props.record.data.state;
        if (state !== 'draft') {
            this.notification.add(
                _t("No se pueden cargar productos a una solicitud de cotización que no está en estado Borrador."),
                { type: "danger" }
            );
            return;
        }

        try {
            const refreshProducts = async () => {
                await new Promise(resolve => setTimeout(resolve, 300));
                await this.fetchProducts(requestQuotationId, { resetHash: true });
            };

            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'purchase.bulk.upload.products.wizard',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    default_request_quotation_id: requestQuotationId,
                }
            }, { onClose: refreshProducts });
        } catch (error) {
            console.error("Error abriendo el asistente de carga masiva", error);
            this.notification.add(
                _t("No se pudo abrir el asistente de carga masiva. Intenta nuevamente."),
                { type: "danger" }
            );
        }
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('es-CO', {
            style: 'currency',
            currency: 'COP',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }

    getWidgetTitle() {
        const typeId = this.props.record.data.type_id;
        if (!typeId || !typeId.display_name) {
            return "Productos";
        }

        const typeName = typeId.display_name;

        if (typeName.includes("Productos")) {
            return "Productos";
        } else if (typeName.includes("Servicios")) {
            return "Servicios";
        } else if (typeName.includes("Mixtos")) {
            return "Elementos solicitados";
        }

        return "Productos";
    }

    getEmptyStateTitle() {
        const typeId = this.props.record.data.type_id;

        let itemType = 'productos';
        if (typeId && typeId.display_name) {
            const typeName = typeId.display_name;
            if (typeName.includes("Servicios")) {
                itemType = 'servicios';
            } else if (typeName.includes("Mixtos")) {
                itemType = 'ítems';
            }
        }

        return `No hay ${itemType} registrados`;
    }

    getEmptyStateDescription() {
        const typeId = this.props.record.data.type_id;
        let itemType = 'productos';
        if (typeId && typeId.display_name) {
            const typeName = typeId.display_name;
            if (typeName.includes("Servicios")) {
                itemType = 'servicios';
            } else if (typeName.includes("Mixtos")) {
                itemType = 'ítems';
            }
        }

        return markup(`
            Tienes flexibilidad para registrar la información: puedes crear cada registro manualmente paso a paso con el botón <strong><i class="fa fa-plus"></i></strong>, 
            o si ya tienes un listado, impórtalo rápidamente desde un archivo Excel usando el botón de carga <strong><i class="fa fa-upload"></i></strong>.
        `);
    }

}

registry.category("fields").add("ProductBoard", {
    component: RequestQuotationProductBoardWidget,
    displayName: "Widget de productos de solicitud de cotización",
    supportedTypes: RequestQuotationProductBoardWidget.supportedTypes,
});
