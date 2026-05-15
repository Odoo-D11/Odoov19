/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { deserializeDateTime } from "@web/core/l10n/dates";

const TIMELINE_NOTIFICATION_TYPE = "expense.timeline/update";

class DisplacementTimelineWidget extends Component {
    static template = "expense.DisplacementTimelineWidget";
    static supportedTypes = ["one2many"];

    setup() {
        super.setup();
        this.isDestroyed = false;
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.state = useState({
            trips: [],
            currentIndex: 0,
            lastUpdateHash: "",
            loading: this.hasDisplacements(),
        });

        this._displacementKey = JSON.stringify(
            this.props.record.data.displacement_ids?.resIds || []
        );
        this._currentExpenseId = this.props.record.resId || this.props.record._config?.resId || false;
        this._fallbackTimer = null;
        this._fallbackActive = false;
        this.fallbackDelay = 15000;
        this._connectedChannel = null;
        this._loadVersion = 0;

        this._handleTimelineNotification = this.onTimelineNotification.bind(this);
        this._onVisibilityChange = () => {
            if (document.hidden) {
                this.stopFallbackPolling();
            } else if (!this.busService.isActive) {
                this.startFallbackPolling();
            }
        };
        this._onBusConnect = () => this.stopFallbackPolling();
        this._onBusReconnect = () => {
            this.stopFallbackPolling();
            this._connectedChannel = null;
            this._ensureTimelineChannel(this._currentExpenseId);
        };
        this._onBusDisconnect = () => {
            this._connectedChannel = null;
            this.startFallbackPolling();
        };

        this.busService.subscribe(TIMELINE_NOTIFICATION_TYPE, this._handleTimelineNotification);
        this.busService.addEventListener("connect", this._onBusConnect);
        this.busService.addEventListener("reconnect", this._onBusReconnect);
        this.busService.addEventListener("disconnect", this._onBusDisconnect);
        document.addEventListener("visibilitychange", this._onVisibilityChange);

        onWillStart(async () => {
            this.state.loading = this.hasDisplacements();
            await this.loadTrips(undefined, { resetIndex: true });
            await this._ensureTimelineChannel(this._currentExpenseId);
        });

        onMounted(() => {
            if (!this.busService.isActive) {
                this.startFallbackPolling();
            }
        });

        onWillUnmount(() => {
            this.isDestroyed = true;
            this.stopFallbackPolling();
            document.removeEventListener("visibilitychange", this._onVisibilityChange);
            this.busService.unsubscribe(TIMELINE_NOTIFICATION_TYPE, this._handleTimelineNotification);
            this.busService.removeEventListener("connect", this._onBusConnect);
            this.busService.removeEventListener("reconnect", this._onBusReconnect);
            this.busService.removeEventListener("disconnect", this._onBusDisconnect);
            this._disconnectTimelineChannel();
        });

        onWillUpdateProps(async (nextProps) => {
            try {
                const newKey = JSON.stringify(
                    nextProps.record.data.displacement_ids?.resIds || []
                );
                const newExpenseId = nextProps.record.resId || nextProps.record._config?.resId || false;
                if (newKey !== this._displacementKey || newExpenseId !== this._currentExpenseId) {
                    this._displacementKey = newKey;
                    this._currentExpenseId = newExpenseId;
                    try {
                        this.state.trips = [];
                        this.state.currentIndex = 0;
                        this.state.lastUpdateHash = "";
                        this.state.loading = this.hasDisplacements(nextProps);
                    } catch (e) { /* componente destruido */ }
                    await this.loadTrips(newExpenseId, { resetIndex: true, props: nextProps });
                    await this._ensureTimelineChannel(newExpenseId);
                }
            } catch (error) {
                console.error("Error actualizando Timeline:", error);
                try { this.state.loading = false; } catch (e) { /* componente destruido */ }
            }
        });
    }

    async checkForUpdates() {
        if (document.hidden || this.isDestroyed) return;
        const expenseId = this.props.record.resId || this.props.record._config?.resId || false;
        if (!expenseId) return;
        try {
            const result = await this.orm.call(
                "expense.expense",
                "get_displacement_hash",
                [expenseId]
            );
            if (this.isDestroyed) return;
            const currentId = this.props.record.resId || this.props.record._config?.resId || false;
            if (expenseId !== currentId) return;
            const serverHash = result?.hash || '';
            if (serverHash && serverHash !== this.state.lastUpdateHash) {
                this.state.lastUpdateHash = serverHash;
                await this.loadTrips(expenseId);
            }
        } catch (error) {
            if (this.isDestroyed || this._isComponentDestroyedError(error)) return;
            console.error('Error al verificar actualizaciones del timeline:', error);
        }
    }

    async loadTrips(
        expenseId = this.props.record.resId || this.props.record._config?.resId || false,
        { resetIndex = false, props = this.props } = {}
    ) {
        const loadVersion = ++this._loadVersion;
        if (this.isDestroyed) return;
        try { this.state.loading = this.hasDisplacements(props); } catch (e) { /* componente destruido */ }

        if (!expenseId) {
            try {
                this.state.trips = [];
                this.state.currentIndex = 0;
                this.state.lastUpdateHash = "";
                this.state.loading = false;
            } catch (e) { /* componente destruido */ }
            return;
        }
        try {
            const data = await this.orm.call("expense.expense", "get_displacement_data", [expenseId]);
            if (this.isDestroyed || loadVersion !== this._loadVersion) return;

            const { displacements: records, service_lines: services, services: serviceDetails } = data;

            const serviceNameById = Object.fromEntries(serviceDetails.map(s => [s.id, s.name]));
            const serviceLineMap = Object.fromEntries(
                services.map(s => [s.id, {
                    id: s.service_id[0],
                    name: serviceNameById[s.service_id[0]],
                    amount: s.total_amount || 0
                }])
            );

            if (this.isDestroyed || loadVersion !== this._loadVersion) return;

            this.state.trips = records.map(r => ({
                ...r,
                services: r.service_line_ids.map(id => serviceLineMap[id]).filter(Boolean),
            }));

            if (this.state.currentIndex >= records.length) {
                this.state.currentIndex = Math.max(0, records.length - 1);
            }
        } catch (error) {
            if (this.isDestroyed || loadVersion !== this._loadVersion) return;
            if (this._isComponentDestroyedError(error)) return;
            this.notification.add("Error al cargar los desplazamientos", { type: "danger" });
            console.error('Error al cargar desplazamientos:', error);
        } finally {
            try {
                if (!this.isDestroyed && loadVersion === this._loadVersion) {
                    this.state.loading = false;
                }
            } catch (e) { /* componente destruido */ }
        }
    }

    formatDateRange(startDateTime, endDateTime) {
        if (!startDateTime || !endDateTime) return "";
        try {
            const start = deserializeDateTime(startDateTime).startOf("day");
            const end = deserializeDateTime(endDateTime).startOf("day");
            const startStr = start.toFormat("dd/LL/yyyy");
            const endStr = end.toFormat("dd/LL/yyyy");
            return start.hasSame(end, "day") ? startStr : `${startStr} - ${endStr}`;
        } catch (error) {
            console.warn("Error formateando rango de fechas:", error);
            return "";
        }
    }

    formatDate(dateTimeStr) {
        if (!dateTimeStr) return "";
        try {
            return deserializeDateTime(dateTimeStr).startOf("day").toFormat("dd/LL/yyyy");
        } catch (error) {
            console.warn("Error formateando fecha:", error);
            return dateTimeStr;
        }
    }

    getDuration(startDateTime, endDateTime) {
        if (!startDateTime || !endDateTime) return "";
        try {
            const start = deserializeDateTime(startDateTime).startOf("day");
            const end = deserializeDateTime(endDateTime).startOf("day");
            const totalDays = Math.round(end.diff(start, "days").days + 1);
            return totalDays === 1 ? "1 día" : `${totalDays} días`;
        } catch (error) {
            console.warn("Error calculando duración:", error);
            return "";
        }
    }

    async onAddTrip() {
        const categoryId = this.props.record.data.category_id;
        const expenseId = this.props.record.resId || this.props.record._config?.resId || false;
        const state = this.props.record.data.state;
        if (!expenseId) {
            this.notification.add(
                "Para agregar un desplazamiento, primero debe guardar la solicitud. Por favor, verifique e intente nuevamente.",
                { type: "danger" }
            );
            return;
        }
        if (state !== 'draft') {
            this.notification.add(
                "No se pueden agregar desplazamientos a una solicitud que no esté en estado Borrador",
                { type: "danger" }
            );
            return;
        }
        if (!categoryId || !categoryId.id) {
            this.notification.add(
                "Debe asignar una categoría a la solicitud antes de agregar un desplazamiento",
                { type: "danger" }
            );
            return;
        }
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "expense.displacement",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: { default_expense_id: expenseId },
                name: "Odoo",
            },
            { onClose: async () => await this.loadTrips() }
        );
    }

    async onOpenTrip(tripId) {
        await this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "expense.displacement",
                res_id: tripId,
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                context: {},
                name: "Odoo",
            },
            { onClose: async () => await this.loadTrips() }
        );
    }

    getCurrentTrip() {
        return this.state.trips[this.state.currentIndex] || null;
    }

    getCounterText() {
        if (!this.state.trips.length) return '';
        return `${this.state.currentIndex + 1}/${this.state.trips.length}`;
    }

    previousTrip() {
        if (this.state.currentIndex > 0) this.state.currentIndex--;
    }

    nextTrip() {
        if (this.state.currentIndex < this.state.trips.length - 1) this.state.currentIndex++;
    }

    onDeleteTrip(tripId) {
        if (this.props.record.data.state !== 'draft') {
            this.notification.add(
                "No se puede eliminar el desplazamiento porque la solicitud no está en estado borrador.",
                { type: "danger" }
            );
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            body: "¿Está seguro de que desea eliminar este desplazamiento?",
            confirm: async () => {
                try {
                    await this.orm.unlink("expense.displacement", [tripId]);
                    await this.loadTrips();
                    this.notification.add("Desplazamiento eliminado correctamente", { type: "success" });
                } catch (error) {
                    this.notification.add("Error al eliminar el desplazamiento", { type: "danger" });
                    console.error('Error al eliminar desplazamiento:', error);
                }
            },
            cancel: () => {},
        });
    }

    getTotalServicesAmount() {
        return this.state.trips.reduce((sum, trip) => sum + trip.services.length, 0);
    }

    getTotalAmount() {
        return this.state.trips.reduce((sum, trip) =>
            sum + trip.services.reduce((s, svc) => s + (svc.amount || 0), 0), 0
        );
    }

    getTripTotalAmount(trip) {
        return trip.services.reduce((sum, svc) => sum + (svc.amount || 0), 0);
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('es-CO', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }

    hasDisplacements(props = this.props) {
        return (props.record.data.displacement_ids?.resIds || []).length > 0;
    }

    _isComponentDestroyedError(error) {
        return error?.message?.includes('Component is destroyed');
    }

    async onTimelineNotification(payload) {
        if (this.isDestroyed) return;
        const expenseId = this.props.record.resId || this.props.record._config?.resId || false;
        if (!payload || !expenseId || payload.expense_id !== expenseId) return;
        await this.loadTrips(expenseId);
    }

    getTimelineChannelName(expenseId) {
        return `expense_timeline_${expenseId}`;
    }

    async _ensureTimelineChannel(expenseId) {
        const expectedChannel = expenseId ? this.getTimelineChannelName(expenseId) : null;
        if (this._connectedChannel === expectedChannel) return;
        this._disconnectTimelineChannel();
        if (!expectedChannel) {
            this.stopFallbackPolling();
            return;
        }
        try {
            await this.busService.addChannel(expectedChannel);
            this._connectedChannel = expectedChannel;
            this.stopFallbackPolling();
        } catch (error) {
            console.error('Error suscribiéndose al canal del timeline:', error);
            this.startFallbackPolling();
        }
    }

    _disconnectTimelineChannel() {
        if (this._connectedChannel) {
            this.busService.deleteChannel(this._connectedChannel);
            this._connectedChannel = null;
        }
    }

    startFallbackPolling() {
        if (this._fallbackActive || this.isDestroyed) return;
        if (!(this.props.record.resId || this.props.record._config?.resId)) return;
        this._fallbackActive = true;
        this.fallbackDelay = 15000;
        const poll = async () => {
            if (!this._fallbackActive) return;
            const prevHash = this.state.lastUpdateHash;
            await this.checkForUpdates();
            if (!this._fallbackActive) return;
            if (this.state.lastUpdateHash !== prevHash) {
                this.fallbackDelay = 15000;
            } else {
                this.fallbackDelay = Math.min(this.fallbackDelay * 1.5, 120000);
            }
            this._fallbackTimer = setTimeout(poll, this.fallbackDelay);
        };
        this._fallbackTimer = setTimeout(poll, this.fallbackDelay);
    }

    stopFallbackPolling() {
        this._fallbackActive = false;
        if (this._fallbackTimer) {
            clearTimeout(this._fallbackTimer);
            this._fallbackTimer = null;
        }
        this.fallbackDelay = 15000;
    }
}

registry.category("fields").add("Timeline", {
    component: DisplacementTimelineWidget,
});
