/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, onWillUnmount, onWillUpdateProps, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const EXPENSE_LINE_NOTIFICATION_TYPE = "administrative_expense.line/update";

class AdminExpenseBoardWidget extends Component {
    static template = "purchase_management.AdminExpenseBoardWidget";
    static supportedTypes = ["one2many"];

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.busService = useService("bus_service");

        this.state = useState({
            lines: [],
            loading: false,
        });

        this.expenseId = this.props.record.resId || false;
        this.lineKey = JSON.stringify(
            this.props.record.data.product_line_ids?.resIds || []
        );
        this.loadVersion = 0;
        this.activeChannel = null;
        this.fallbackTimer = null;
        this.fallbackDelay = 15000;
        this.maxFallbackDelay = 120000;

        this.handleNotification = this._handleNotification.bind(this);

        this.busService.subscribe(EXPENSE_LINE_NOTIFICATION_TYPE, this.handleNotification);

        this.onBusConnect = () => { this._stopFallbackPolling(); };
        this.onBusReconnect = () => {
            this._stopFallbackPolling();
            this.activeChannel = null;
            this._ensureChannel(this.expenseId);
        };
        this.onBusDisconnect = () => {
            this.activeChannel = null;
            this._startFallbackPolling();
        };
        for (const [ev, fn] of Object.entries({
            connect: this.onBusConnect,
            reconnect: this.onBusReconnect,
            disconnect: this.onBusDisconnect,
        })) {
            this.busService.addEventListener(ev, fn);
        }
        this._busHandlers = { connect: this.onBusConnect, reconnect: this.onBusReconnect, disconnect: this.onBusDisconnect };

        this._onVisibilityChange = () => {
            if (document.hidden) {
                this._stopFallbackPolling();
            } else if (!this.busService.isActive) {
                this.fallbackDelay = 15000;
                this._startFallbackPolling();
            }
        };
        document.addEventListener('visibilitychange', this._onVisibilityChange);

        onWillStart(async () => {
            try {
                await this.fetchLines();
                await this._ensureChannel(this.expenseId);
            } catch (error) {
                console.error("Error inicializando AdminExpenseBoard:", error);
                this.state.loading = false;
            }
        });

        onMounted(() => {
            if (!this.busService.isActive) {
                this._startFallbackPolling();
            }
        });

        onWillUnmount(() => {
            this._stopFallbackPolling();
            this.busService.unsubscribe(EXPENSE_LINE_NOTIFICATION_TYPE, this.handleNotification);
            for (const [ev, fn] of Object.entries(this._busHandlers)) {
                this.busService.removeEventListener(ev, fn);
            }
            this._disconnectChannel();
            document.removeEventListener('visibilitychange', this._onVisibilityChange);
        });

        onWillUpdateProps(async (nextProps) => {
            const newId = nextProps.record.resId;
            const newKey = JSON.stringify(
                nextProps.record.data.product_line_ids?.resIds || []
            );
            const idChanged = newId !== this.expenseId;
            const linesChanged = newKey !== this.lineKey;
            this.lineKey = newKey;
            if (idChanged) {
                this.expenseId = newId;
            }
            if (idChanged || linesChanged) {
                await this.fetchLines();
                if (idChanged) await this._ensureChannel(newId);
            }
        });
    }

    // ─── Bus / polling ───────────────────────────────────────────────────────

    _getChannel(expenseId) {
        return `administrative_expense_lines_${expenseId}`;
    }

    async _ensureChannel(expenseId) {
        const expected = expenseId ? this._getChannel(expenseId) : null;
        if (this.activeChannel === expected) return;
        this._disconnectChannel();
        if (!expected) { this._stopFallbackPolling(); return; }
        try {
            await this.busService.addChannel(expected);
            this.activeChannel = expected;
            this._stopFallbackPolling();
        } catch {
            this._startFallbackPolling();
        }
    }

    _disconnectChannel() {
        if (this.activeChannel) {
            this.busService.deleteChannel(this.activeChannel);
            this.activeChannel = null;
        }
    }

    async _handleNotification(payload) {
        if (!payload || !this.expenseId || payload.expense_id !== this.expenseId) return;
        await this.fetchLines();
    }

    _startFallbackPolling() {
        if (this.fallbackTimer || !this.expenseId) return;
        const poll = async () => {
            if (document.hidden) return;
            await this.fetchLines();
            if (this.fallbackTimer) {
                clearInterval(this.fallbackTimer);
                this.fallbackTimer = setInterval(poll, this.fallbackDelay);
            }
        };
        poll();
        this.fallbackTimer = setInterval(poll, this.fallbackDelay);
    }

    _stopFallbackPolling() {
        if (this.fallbackTimer) {
            clearInterval(this.fallbackTimer);
            this.fallbackTimer = null;
        }
    }

    // ─── Data ────────────────────────────────────────────────────────────────

    async fetchLines() {
        const loadVersion = ++this.loadVersion;
        if (!this.expenseId) {
            this.state.lines = [];
            this.state.loading = false;
            return;
        }
        try {
            const lines = await this.orm.call(
                "purchase.administrative.expense",
                "get_admin_expense_lines",
                [this.expenseId]
            );
            if (loadVersion !== this.loadVersion) return;
            this.state.lines = lines;
        } catch (error) {
            console.error("Error al cargar las líneas del gasto", error);
        } finally {
            if (loadVersion === this.loadVersion) {
                this.state.loading = false;
            }
        }
    }

    // ─── Getters ─────────────────────────────────────────────────────────────

    hasLines() {
        return this.state.lines.length > 0;
    }

    get totalItems() { return this.state.lines.length; }

    get totalPrice() {
        return this.state.lines.reduce((s, l) => s + (l.subtotal || 0), 0);
    }

    get itemLabel() {
        return this.totalItems === 1 ? "Servicio" : "Servicios";
    }

    get widgetTitle() { return "Servicios"; }

    get emptyTitle() { return "Sin servicios registrados"; }

    get emptyDescription() {
        return "No hay servicios aún. Haz clic en + para agregar los ítems de este gasto.";
    }

    formatPrice(amount) {
        return new Intl.NumberFormat("es-CO", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(amount);
    }

    get showAddButton() { return this.state.lines.length === 0; }
    get showBulkUploadButton() { return false; }
    get showToggleButton() { return false; }

    // ─── Actions ─────────────────────────────────────────────────────────────

    async _getExpenseLineViewId() {
        if (this._cachedViewId !== undefined) return this._cachedViewId;
        const viewId = await this.orm.call(
            "purchase.administrative.expense",
            "get_expense_line_view_id",
            []
        );
        this._cachedViewId = viewId;
        return viewId;
    }

    async _openServiceManager() {
        if (!this.expenseId) {
            this.notification.add(
                _t("Para gestionar servicios, primero debe guardar el gasto."),
                { type: "danger" }
            );
            return;
        }
        const viewId = await this._getExpenseLineViewId();
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "purchase.administrative.expense",
                view_mode: "form",
                views: [[viewId || false, "form"]],
                target: "new",
                res_id: this.expenseId,
                name: "Odoo",
            },
            {
                onClose: async () => {
                    await this.fetchLines();
                },
            }
        );
    }

    async openProductManager() {
        await this._openServiceManager();
    }

    async addProductLine() {
        await this._openServiceManager();
    }

    onToggleWidget() {}
}

registry.category("fields").add("AdminExpenseBoard", {
    component: AdminExpenseBoardWidget,
    displayName: "Widget de servicios de gasto administrativo",
    supportedTypes: AdminExpenseBoardWidget.supportedTypes,
});
