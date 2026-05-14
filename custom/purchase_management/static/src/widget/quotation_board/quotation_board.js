/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registerWidget, toggleActiveWidget, setDefaultWidget } from "../shared/board_switcher";

const QUOTATION_NOTIFICATION_TYPE = "quotation.quotation/update";


class QuotationBoardWidget extends Component {
    static template = "purchase_management.QuotationBoardWidget";
    static supportedTypes = ["one2many"];

    setup() {
        super.setup();
        this.isDestroyed = false;
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.boardCache = useService("purchase_management.board_cache");

        if (!this.props.record) {
            console.warn("QuotationBoard: No record found in props");
            this.state = useState({ quotationLines: [], currentIndex: 0, lastUpdateHash: "", loading: false, isVisible: false, canCreateQuotation: false });
            return;
        }

        this.quotationId = this.props.record.resId || this.props.record._config?.resId || false;
        this.modelName = this.props.record.resModel || "request.quotation";

        this.state = useState({
            quotationLines: [],
            currentIndex: 0,
            lastUpdateHash: "",
            loading: this.hasQuotationLines(),
            isVisible: false,
            canCreateQuotation: false,
        });

        const recordData = this.props.record.data || {};
        const recordState = recordData.state || "draft";
        const allQuotationRejected = recordData.all_quotation_rejected || false;
        const commiteeApprovalRejected = recordData.commitee_approval_rejected || false;

        setDefaultWidget(recordState, this.quotationId, {
            allQuotationRejected,
            commiteeApprovalRejected
        });

        this.unregisterVisibility = registerWidget("supplier", (isVisible) => {
            if (this.state) {
                this.state.isVisible = isVisible;
            }
        });

        this.quotationLineKey = JSON.stringify(recordData.quotation_line_ids?.resIds || []);
        this.fallbackPollingTimer = null;
        this.fallbackPollingDelay = 15000;
        this.maxPollingDelay = 120000;
        this.activeQuotationChannel = null;
        this.handleQuotationNotification = this.handleQuotationLineNotification.bind(this);
        this.onBusConnect = () => {
            this.stopQuotationFallbackPolling();
        };
        this.onBusReconnect = () => {
            this.stopQuotationFallbackPolling();
            this.activeQuotationChannel = null;
            this.ensureQuotationLineChannel(this.quotationId);
        };
        this.onBusDisconnect = () => {
            this.activeQuotationChannel = null;
            this.startQuotationFallbackPolling();
        };
        this.busEventHandlers = {
            connect: this.onBusConnect,
            reconnect: this.onBusReconnect,
            disconnect: this.onBusDisconnect,
        };
        this.loadVersion = 0;
        this._lastFetchTimestamp = 0;

        this.busService.subscribe(
            QUOTATION_NOTIFICATION_TYPE,
            this.handleQuotationNotification
        );
        for (const [event, handler] of Object.entries(this.busEventHandlers)) {
            this.busService.addEventListener(event, handler);
        }

        this._onVisibilityChange = () => {
            if (document.hidden) {
                this.stopQuotationFallbackPolling();
            } else if (!this.busService.isActive) {
                this.fallbackPollingDelay = 15000;
                this.startQuotationFallbackPolling();
            }
        };
        document.addEventListener('visibilitychange', this._onVisibilityChange);

        onWillStart(async () => {
            try {
                this.state.loading = this.hasQuotationLines();
                const [, canCreate] = await Promise.all([
                    this.fetchQuotationLinesFromBoard(this.quotationId, { resetIndex: true }),
                    this.orm.call('request.quotation', 'is_purchase_member', []),
                ]);
                this.state.canCreateQuotation = canCreate;
            } catch (error) {
                console.error("Error inicializando QuotationBoard:", error);
                this.state.loading = false;
                this.state.canCreateQuotation = false;
            }
        });

        onMounted(async () => {
            try {
                await this.ensureQuotationLineChannel(this.quotationId);
            } catch (error) {
                console.error("Error suscribiéndose al canal de cotizaciones en mount:", error);
            }
            if (!this.busService.isActive) {
                this.startQuotationFallbackPolling();
            }
        });

        onWillUnmount(() => {
            this.isDestroyed = true;
            this.stopQuotationFallbackPolling();
            this.busService.unsubscribe(
                QUOTATION_NOTIFICATION_TYPE,
                this.handleQuotationNotification
            );
            for (const [event, handler] of Object.entries(this.busEventHandlers)) {
                this.busService.removeEventListener(event, handler);
            }
            this.disconnectQuotationLineChannel();
            this.unregisterVisibility?.();
            document.removeEventListener('visibilitychange', this._onVisibilityChange);
        });

        onWillUpdateProps(async (nextProps) => {
            try {
                if (!nextProps.record || !nextProps.record.data) {
                    return;
                }
                const nextRecordState = nextProps.record.data.state;
                const nextRecordId = nextProps.record.resId || false;

                setDefaultWidget(nextRecordState, nextRecordId, {
                    allQuotationRejected: nextProps.record.data.all_quotation_rejected,
                    commiteeApprovalRejected: nextProps.record.data.commitee_approval_rejected
                });

                const newKey = JSON.stringify(
                    nextProps.record.data.quotation_line_ids?.resIds || []
                );
                const newQuotationId = nextProps.record.resId;
                if (newKey !== this.quotationLineKey || newQuotationId !== this.quotationId) {
                    const now = Date.now();
                    if (now - this._lastFetchTimestamp < 500) {
                        this.quotationLineKey = newKey;
                        this.quotationId = newQuotationId;
                        return;
                    }
                    this._lastFetchTimestamp = now;
                    this.quotationLineKey = newKey;
                    this.quotationId = newQuotationId;

                    this.state.quotationLines = [];
                    this.state.currentIndex = 0;
                    this.state.lastUpdateHash = "";
                    this.state.loading = this.hasQuotationLines(nextProps);
                    await this.fetchQuotationLines(newQuotationId, { resetIndex: true, props: nextProps });
                    await this.ensureQuotationLineChannel(newQuotationId);
                }
            } catch (error) {
                console.error("Error actualizando QuotationBoard:", error);
                try { this.state.loading = false; } catch (e) { /* componente destruido */ }
            }
        });
    }

    _isComponentDestroyedError(error) {
        return error?.message?.includes('Component is destroyed');
    }

    async fetchQuotationLinesFromBoard(
        quotationId = this.props.record.resId,
        { resetIndex = false, props = this.props } = {}
    ) {
        const loadVersion = ++this.loadVersion;
        if (this.isDestroyed) return;
        this.state.loading = this.hasQuotationLines(props);
        
        if (!quotationId) {
            if (this.isDestroyed) return;
            Object.assign(this.state, { quotationLines: [], currentIndex: 0, lastUpdateHash: "", loading: false });
            return;
        }
        try {
            const boardData = await this.boardCache.getBoardData(quotationId, this.modelName);
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            if (quotationId !== (this.props.record.resId || this.props.record._config?.resId)) return;
            
            const quotationRecords = boardData.quotations || [];
            const serviceLines = boardData.quotation_products || [];

            const serviceLineMap = Object.fromEntries(
                serviceLines.map(line => [
                    line.id,
                    {
                        name: line.name || "",
                        subtotal: line.subtotal || 0,
                        displayType: line.display_type || null,
                    },
                ])
            );
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;

            const nextLines = quotationRecords.map(record => {
                const lineIds = Array.isArray(record.product_line_ids) ? record.product_line_ids : [];
                return {
                    ...record,
                    services: lineIds
                        .map(serviceId => serviceLineMap[serviceId])
                        .filter(Boolean),
                    hasObservations: Array.isArray(record.purchase_observation_recommendation_ids) && record.purchase_observation_recommendation_ids.length > 0,
                };
            });
            
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            
            this.state.quotationLines = nextLines;
            if (this.state.currentIndex >= this.state.quotationLines.length) {
                this.state.currentIndex = Math.max(0, this.state.quotationLines.length - 1);
            }
        } catch (error) {
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            if (this._isComponentDestroyedError(error)) return;
            console.warn('Error al cargar board data, usando fallback:', error);
            await this.fetchQuotationLines(quotationId, { resetIndex, props });
        } finally {
            try {
                if (!this.isDestroyed && loadVersion === this.loadVersion) {
                    this.state.loading = false;
                }
            } catch (e) { /* componente destruido */ }
        }
    }

    async fetchQuotationUpdates() {
        const quotationId = this.props.record.resId;
        if (!quotationId || this.isDestroyed) return;

        try {
            const result = await this.orm.call(
                this.modelName,
                "get_board_update_hash",
                [quotationId]
            );
            if (this.isDestroyed || quotationId !== this.props.record.resId) return;

            const serverHash = result.hash || '';
            if (serverHash && serverHash !== this.state.lastUpdateHash) {
                this.state.lastUpdateHash = serverHash;
                await this.fetchQuotationLines(quotationId);
            }
        } catch (error) {
            console.error('Error al obtener las actualizaciones:', error);
        }
    }

    onToggleWidget() {
        toggleActiveWidget();
    }

    async fetchQuotationLines(
        quotationId = this.props.record.resId,
        { resetIndex = false, props = this.props } = {}
    ) {
        const loadVersion = ++this.loadVersion;
        if (this.isDestroyed) return;
        this.state.loading = this.hasQuotationLines(props);
        
        if (!quotationId) {
            if (this.isDestroyed) return;
            Object.assign(this.state, { quotationLines: [], currentIndex: 0, lastUpdateHash: "", loading: false });
            return;
        }
        try {
            const quotationRecords = await this.orm.searchRead(
                "quotation.quotation",
                [["request_quotation_id", "=", quotationId]],
                ["id", "write_date", "product_line_ids", "supplier_name", "validity_date", "delivery_date", "payment_term", "currency_id",
                    "observation_ids", "trm", "purchase_observation_recommendation_ids"]
            );
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;

            const quotationLineProductIds = quotationRecords.flatMap(record => 
                Array.isArray(record.product_line_ids) ? record.product_line_ids : []
            );
            
            const serviceLines = quotationLineProductIds.length
                ? await this.orm.searchRead(
                    "product.quotation.line",
                    [["id", "in", quotationLineProductIds]],
                    ["id", "name", "subtotal", "display_type"]
                )
                : [];
                
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;

            const serviceLineMap = Object.fromEntries(
                serviceLines.map(line => [
                    line.id,
                    {
                        name: line.name || "",
                        subtotal: line.subtotal || 0,
                        displayType: line.display_type || null,
                    },
                ])
            );
            
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;

            this.state.quotationLines = quotationRecords.map(record => {
                const lineIds = Array.isArray(record.product_line_ids) ? record.product_line_ids : [];
                return {
                    ...record,
                    services: lineIds
                        .map(serviceId => serviceLineMap[serviceId])
                        .filter(Boolean),
                    hasObservations: Array.isArray(record.purchase_observation_recommendation_ids) && record.purchase_observation_recommendation_ids.length > 0,
                };
            });
            
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            if (this.state.currentIndex >= this.state.quotationLines.length) {
                this.state.currentIndex = Math.max(0, this.state.quotationLines.length - 1);
            }
        } catch (error) {
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            if (this._isComponentDestroyedError(error)) return;
            this.notification.add("Error al cargar la lista de productos de los proveedores", { type: "danger" });
            console.error('Error al cargar la lista de productos de los proveedores:', error);
        } finally {
            try {
                if (!this.isDestroyed && loadVersion === this.loadVersion) {
                    this.state.loading = false;
                }
            } catch (e) { /* componente destruido */ }
        }
    }

    async addQuotationLine() {
        const typeId = this.props.record.data.type_id;
        const quotationId = this.props.record.resId;
        const state = this.props.record.data.state;

        if (!quotationId) {
            this.notification.add(
                "Para agregar un proveedor, primero debe guardar la solicitud de cotización. Por favor, verifique e intente nuevamente.",
                { type: "danger" }
            );
            return;
        }
        if (!['sent', 'in_shopping'].includes(state)) {
            this.notification.add(
                "No se pueden agregar proveedores a una solicitud de cotización que no esté en estado Enviada o En Compras",
                { type: "danger" }
            );
            return;
        }
        if (!typeId || !typeId.id) {
            this.notification.add(
                "Debe asignar un tipo de solicitud a la solicitud de cotización antes de agregar un proveedor",
                { type: "danger" }
            );
            return;
        }

        const typeNameStr = typeId.display_name || '';
        let typeString = 'product';
        if (typeNameStr === 'Servicios' || typeNameStr.includes('Servicios')) {
            typeString = 'service';
        } else if (typeNameStr === 'Mixtos' || typeNameStr.includes('Mixtos')) {
            typeString = 'mix';
        }

        const requestQuotationLineIds = await this.orm.searchRead(
            "request.product.quotation.line",
            [["request_quotation_id", "=", quotationId]],
            ["qty", "name", "uom_id", "display_type", "product_name", "sequence"],
            { order: "sequence, id" }
        );

        // Separar productos y notas
        const products = requestQuotationLineIds.filter(l => l.display_type !== 'line_note');
        const notes    = requestQuotationLineIds.filter(l => l.display_type === 'line_note');

        // Construir mapa de notas por product_name (array para manejar nombres duplicados).
        // Se usa clave en minúsculas para comparación robusta.
        const notesByProductName = {};
        for (const note of notes) {
            const key = (note.product_name || '').trim().toLowerCase();
            if (key) {
                if (!notesByProductName[key]) notesByProductName[key] = [];
                notesByProductName[key].push(note);
            }
        }

        // Construir array ordenado: producto seguido de su nota (si existe).
        // shift() consume la primera nota coincidente, preservando el orden correcto
        // para productos con nombre duplicado (e.g., dos "Toner" distintos).
        const orderedLines = [];
        let sequenceCounter = 1;

        for (const product of products) {
            orderedLines.push([0, 0, {
                request_line_id: product.id,
                name: product.name,
                qty: product.qty,
                uom_id: product.uom_id?.[0] || false,
                sequence: sequenceCounter++,
            }]);

            const key = (product.name || '').trim().toLowerCase();
            const matchingNotes = notesByProductName[key] || [];
            if (matchingNotes.length > 0) {
                const note = matchingNotes.shift(); // primer nota coincidente (FIFO)
                orderedLines.push([0, 0, {
                    display_type: 'line_note',
                    name: note.name,
                    product_name: product.name,
                    sequence: sequenceCounter++,
                }]);
            }
        }

        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "quotation.quotation",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_request_quotation_id: this.props.record.resId,
                default_type: typeString,
                default_product_line_ids: orderedLines,
            },
            name: "Odoo",
        }, {
            onClose: async () => {
                await this.fetchQuotationLines();
            },
        });
    }

    async openQuotationLine(quotationLineId) {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "quotation.quotation",
            res_id: quotationLineId,
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_request_quotation_id: this.props.record.resId,
            },
            name: "Odoo",
        }, {
            onClose: async () => {
                await this.fetchQuotationLines();
            },
        });
    }

    getCurrentQuotationLine() {
        return this.state.quotationLines[this.state.currentIndex] || null;
    }

    getCounterText() {
        if (!this.state.quotationLines.length) return '';
        return `${this.state.currentIndex + 1}/${this.state.quotationLines.length}`;
    }

    previousQuotationLine() {
        if (this.state.currentIndex > 0) {
            this.state.currentIndex--;
        }
    }

    nextQuotationLine() {
        if (this.state.currentIndex < this.state.quotationLines.length - 1) {
            this.state.currentIndex++;
        }
    }

    deleteQuotationLine(quotationLineId) {
        const state = this.props.record.data.state;
        if (state !== 'sent' && state !== 'in_shopping') {
            this.notification.add("No se puede eliminar la línea de cotización porque la solicitud no está en estado enviada o en compras.",
                { type: "danger" });
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            body: "¿Está seguro de que desea eliminar esta línea de cotización?",
            confirm: async () => {
                try {
                    await this.orm.unlink("quotation.quotation", [quotationLineId]);
                    await this.fetchQuotationLines();
                    this.notification.add(
                        "Línea de cotización eliminada correctamente",
                        { type: "success" }
                    );
                } catch (error) {
                    this.notification.add(
                        "Error al eliminar la línea de cotización. Por favor, intente nuevamente.",
                        { type: "danger" }
                    );
                    console.error('Error deleting quotation line:', error);
                }
            },
            cancel: () => { },
        });
    }

    getTotalServicesAmount() {
        let totalServices = 0;
        this.state.quotationLines.forEach(line => {
            totalServices += line.services.length;
        });
        return totalServices;
    }

    getTotalEstimatedPrice() {
        let totalAmount = 0;
        this.state.quotationLines.forEach(line => {
            line.services.forEach(service => {
                totalAmount += service.subtotal || 0;
            });
        });
        return totalAmount;
    }

    getQuotationLineEstimatedPrice(quotationLine) {
        let quotationLineTotal = 0;
        (quotationLine.services || []).forEach(service => {
            quotationLineTotal += service.subtotal || 0;
        });
        const currency = quotationLine.currency_id?.[1] || null;
        const trmValue = quotationLine.trm || 0;
        let amountInCop = null;
        if (currency && currency !== 'COP' && trmValue > 0) {
            amountInCop = quotationLineTotal * trmValue;
        } else if (currency === 'COP') {
            amountInCop = quotationLineTotal;
        }
        return amountInCop !== null ? amountInCop : quotationLineTotal;
    }

    getQuotationValidityDate(quotationLine) {
        if (!quotationLine.validity_date) return null;

        try {
            const [year, month, day] = quotationLine.validity_date.split('-');
            const date = new Date(year, month - 1, day);
            return date.toLocaleDateString('es-ES', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            });
        } catch (error) {
            return quotationLine.validity_date;
        }
    }

    getFormattedDeliveryDate(quotationLine) {
        if (!quotationLine.delivery_date) return 'Sin fecha';

        try {
            const [year, month, day] = quotationLine.delivery_date.split('-');
            const date = new Date(year, month - 1, day);
            return date.toLocaleDateString('es-ES', {
                day: '2-digit',
                month: '2-digit'
            });
        } catch (error) {
            return quotationLine.delivery_date;
        }
    }

    getFormattedDeliveryDateWithYear(quotationLine) {
        if (!quotationLine.delivery_date) return 'Sin fecha';

        try {
            const [year, month, day] = quotationLine.delivery_date.split('-');
            const date = new Date(year, month - 1, day);
            return date.toLocaleDateString('es-ES', {
                day: '2-digit',
                month: '2-digit',
                year: '2-digit'
            });
        } catch (error) {
            return quotationLine.delivery_date;
        }
    }

    getFormattedValidityDateWithYear(quotationLine) {
        if (!quotationLine.validity_date) return 'Sin fecha';

        try {
            const [year, month, day] = quotationLine.validity_date.split('-');
            const date = new Date(year, month - 1, day);
            return date.toLocaleDateString('es-ES', {
                day: '2-digit',
                month: '2-digit',
                year: '2-digit'
            });
        } catch (error) {
            return quotationLine.validity_date;
        }
    }

    getShortPaymentTerm(quotationLine) {
        if (!quotationLine.payment_term) {
            return 'Sin plazo';
        }

        const paymentTerm = quotationLine.payment_term;

        if (paymentTerm.length > 12) {
            return paymentTerm.substring(0, 9) + '...';
        }

        return paymentTerm;
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('es-CO', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }

    hasQuotationLines(props = this.props) {
        return (props.record.data.quotation_line_ids?.resIds || []).length > 0;
    }

    async handleQuotationLineNotification(payload) {
        if (this.isDestroyed) return;
        
        let quotationId;
        try {
            quotationId = this.props.record.resId || this.props.record._config?.resId;
        } catch (e) {
            return;
        }

        if (
            !payload ||
            !quotationId ||
            payload.quotation_id !== quotationId
        ) {
            return;
        }
        await this.fetchQuotationLines(quotationId);
    }

    getQuotationLineChannel(quotationId) {
        return `quotation_line${quotationId}`;
    }

    async ensureQuotationLineChannel(quotationId) {
        const quotationChannel = quotationId ? this.getQuotationLineChannel(quotationId) : null;

        if (this.activeQuotationChannel === quotationChannel) {
            return;
        }

        this.disconnectQuotationLineChannel();

        if (!quotationChannel) {
            this.stopQuotationFallbackPolling();
            return;
        }

        try {
            await this.busService.addChannel(quotationChannel);
            this.activeQuotationChannel = quotationChannel;
            this.stopQuotationFallbackPolling();
        } catch (error) {
            console.error('Error suscribiéndose al canal del timeline:', error);
            this.startQuotationFallbackPolling();
        }
    }

    disconnectQuotationLineChannel() {
        if (this.activeQuotationChannel) {
            this.busService.deleteChannel(this.activeQuotationChannel);
            this.activeQuotationChannel = null;
        }
    }

    startQuotationFallbackPolling() {
        if (this.fallbackPollingTimer) {
            return;
        }
        const quotationId = this.props.record.resId;
        if (!quotationId) {
            return;
        }
        const poll = async () => {
            if (document.hidden) return;
            const prevHash = this.state.lastUpdateHash;
            await this.fetchQuotationUpdates();
            if (this.state.lastUpdateHash !== prevHash) {
                this.fallbackPollingDelay = 15000;
            } else {
                this.fallbackPollingDelay = Math.min(this.fallbackPollingDelay * 1.5, this.maxPollingDelay);
            }
            if (this.fallbackPollingTimer) {
                clearInterval(this.fallbackPollingTimer);
                this.fallbackPollingTimer = setInterval(poll, this.fallbackPollingDelay);
            }
        };
        poll();
        this.fallbackPollingTimer = setInterval(poll, this.fallbackPollingDelay);
    }

    stopQuotationFallbackPolling() {
        if (this.fallbackPollingTimer) {
            clearInterval(this.fallbackPollingTimer);
            this.fallbackPollingTimer = null;
        }
    }

    async openObservationsWizard(quotationLineId) {
        try {
            const cachedLine = this.state.quotationLines.find(q => q.id === quotationLineId);
            if (cachedLine && !cachedLine.hasObservations) {
                this.notification.add(
                    "No hay observaciones registradas para esta cotización.",
                    { type: "warning" }
                );
                return;
            }
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "purchase.management.view.observations.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_quotation_id: quotationLineId,
                },
                name: "Odoo",
            });
        } catch (error) {
            this.notification.add(
                "Error al cargar las observaciones.",
                { type: "danger" }
            );
            console.error('Error abriendo observaciones:', error);
        }
    }

    canDeleteQuotation() {
        const rfqState = this.props.record.data.state;
        const allowedStates = ['draft', 'in_shopping', 'sent'];
        return allowedStates.includes(rfqState);
    }

    get showActionsButton() {
        const state = this.props.record.data.state;
        return (state === 'sent' || state === 'in_shopping') && this.state.canCreateQuotation;
    }

    async openImportQuotationWizard() {
        const requestQuotationId = this.props.record.resId;
        if (!requestQuotationId) {
            this.notification.add(
                "Para importar una cotización, primero debe guardar la solicitud de cotización.",
                { type: 'danger' }
            );
            return;
        }

        const state = this.props.record.data.state;
        if (!['sent', 'in_shopping'].includes(state)) {
            this.notification.add(
                "Solo se pueden importar cotizaciones cuando la solicitud está en estado Enviada.",
                { type: "danger" }
            );
            return;
        }

        try {
            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'purchase.bulk.upload.quotations.wizard',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    default_request_quotation_id: requestQuotationId,
                }
            }, {
                onClose: async () => {
                    await this.fetchQuotationLines();
                }
            });
        } catch (error) {
            console.error("Error abriendo el asistente de importación de cotizaciones", error);
            this.notification.add(
                "No se pudo abrir el asistente de importación. Intenta nuevamente.",
                { type: "danger" }
            );
        }
    }
}

registry.category("fields").add("QuotationBoard", {
    component: QuotationBoardWidget,
    displayName: "Widget de Cotización de Proveedores",
});