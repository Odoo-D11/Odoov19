/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Many2OneField, many2OneField } from "@web/views/fields/many2one/many2one_field";
import { Component, useState, onMounted, onWillStart, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";

const DEFAULT_NOTIFICATION_TYPE = "avatar/update";
const DEFAULT_PAYLOAD_KEY = "record_id";
const DEFAULT_EMPLOYEE_MODEL = "hr.employee";
const DEFAULT_FALLBACK_DELAY = 15000;

function toCamelCase(key) {
    return key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function normalizeConfigKeys(config) {
    if (!config || typeof config !== "object") {
        return {};
    }
    const normalized = {};
    for (const [key, value] of Object.entries(config)) {
        const normalizedKey = toCamelCase(key);
        normalized[normalizedKey] = value;
    }
    return normalized;
}


function getEmptyEmployee() {
    return {
        id: null,
        gender: '',
        name: '',
        work_email: '',
        private_email: '',
        mobile_phone: '',
        private_phone: '',
        enterprise_id: null,
        job_title: '',
        identification_type_id: null,
        identification_id: '',
        age: '',
        has_image: false,
    };
}

export class ExpEmployeeCard extends Component {
    static template = "ExpEmployeeCard";
    static props = { employee: Object, close: Function };

    get avatarSrc() {
        const emp = this.props.employee;
        if (!emp || !emp.id) {
            return '';
        }
        if (emp.gender === 'female') {
            return '/utils/static/src/img/female.png';
        }
        if (emp.gender === 'male') {
            return '/utils/static/src/img/male.png';
        }
        if (emp.has_image) {
            return `/web/image/hr.employee/${emp.id}/image_128`;
        }
        return '';
    }
}

export class ExpAvatarPopup extends Many2OneField {
    static template = "ExpAvatarPopupTemplate";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.avatarOptions = {
            notificationType: DEFAULT_NOTIFICATION_TYPE,
            payloadKey: DEFAULT_PAYLOAD_KEY,
            employeeModel: DEFAULT_EMPLOYEE_MODEL,
            relationEmployeeField: null,
            fallbackDelay: DEFAULT_FALLBACK_DELAY,
            channelName: null,
        };
        this.popover = usePopover(ExpEmployeeCard, {
            arrow: true,
            position: "right",
            popoverClass: "exp-employee-popover",
        });
        this.details = useState({
            employee: getEmptyEmployee(),
            ready: false,
            loading: false,
        });
        this._currentRelationId = this._getRelationIdFromProps(this.props);
        this._currentEmployeeId = null;
        this._currentRecordId = this.props.record.resId || null;
        this._currentChannelName = this.avatarOptions.channelName;
        this._loadToken = 0;
        this._connectedChannel = null;
        this._fallbackInterval = null;
        this.fallbackDelay = this.avatarOptions.fallbackDelay;
        this._subscribedNotificationType = null;

        this._handleAvatarNotification = this.onAvatarNotification.bind(this);
        this._busEventHandlers = {
            connect: () => this.stopFallbackPolling(),
            reconnect: () => {
                this.stopFallbackPolling();
                this._connectedChannel = null;
                this.ensureAvatarChannel(this._currentChannelName);
            },
            disconnect: () => {
                this._connectedChannel = null;
                this.startFallbackPolling();
            },
        };

        this._updateNotificationSubscription();
        for (const [event, handler] of Object.entries(this._busEventHandlers)) {
            this.busService.addEventListener(event, handler);
        }

        onWillStart(async () => {
            await this._loadWidgetConfig(this._currentRecordId);
            await this._loadEmployee(this._currentRelationId);
            await this.ensureAvatarChannel(this._currentChannelName);
        });

        onMounted(() => {
            if (!this.busService.isActive) {
                this.startFallbackPolling();
            }
        });

        onWillUnmount(() => {
            this.stopFallbackPolling();
            if (this._subscribedNotificationType) {
                this.busService.unsubscribe(
                    this._subscribedNotificationType,
                    this._handleAvatarNotification
                );
                this._subscribedNotificationType = null;
            }
            for (const [event, handler] of Object.entries(this._busEventHandlers)) {
                this.busService.removeEventListener(event, handler);
            }
            this._disconnectAvatarChannel();
        });

        onWillUpdateProps(async (newProps) => {
            const newRelationId = this._getRelationIdFromProps(newProps);
            const newRecordId = newProps.record.resId || null;

            if (newRecordId !== this._currentRecordId) {
                this._currentRecordId = newRecordId;
                await this._loadWidgetConfig(newRecordId);
            }

            if (newRelationId !== this._currentRelationId) {
                this._currentRelationId = newRelationId;
                await this._loadEmployee(newRelationId);
            }

            if (this.avatarOptions.channelName !== this._currentChannelName) {
                this._currentChannelName = this.avatarOptions.channelName;
                await this.ensureAvatarChannel(this._currentChannelName);
            }
        });
    }

    openCard(ev) {
        if (!this.details.ready || !this.details.employee || !this.details.employee.name) {
            return;
        }
        this.popover.open(ev.currentTarget, { employee: this.details.employee });
    }

    async _loadEmployee(relationId) {
        const loadToken = ++this._loadToken;
        if (!relationId) {
            this._currentEmployeeId = null;
            this.details.employee = getEmptyEmployee();
            this.details.ready = true;
            this.details.loading = false;
            return;
        }
        this.details.loading = true;
        try {
            const readContext = { ...(this.context || {}), bin_size: true };
            const employeeId = await this._resolveEmployeeId(relationId);
            if (loadToken !== this._loadToken) {
                return;
            }
            if (!employeeId) {
                this._currentEmployeeId = null;
                this.details.employee = getEmptyEmployee();
                return;
            }
            this._currentEmployeeId = employeeId;
            const [emp] = await this.orm.searchRead(
                this.avatarOptions.employeeModel,
                [["id", "=", employeeId]],
                [
                    "id",
                    "gender",
                    "name",
                    "work_email",
                    "private_email",
                    "mobile_phone",
                    "private_phone",
                    "enterprise_id",
                    "job_title",
                    "identification_type_id",
                    "identification_id",
                    "age",
                    "image_128",
                ],
                { context: readContext, limit: 1 }
            );
            if (loadToken !== this._loadToken) {
                return;
            }
            if (emp) {
                const { image_128, ...employeeData } = emp;
                const hasImage = Boolean(image_128 && image_128 !== "0");
                this.details.employee = {
                    ...getEmptyEmployee(),
                    ...employeeData,
                    has_image: hasImage,
                };
            } else {
                this.details.employee = getEmptyEmployee();
            }
        } catch (error) {
            if (loadToken === this._loadToken) {
                this.details.employee = getEmptyEmployee();
            }
            console.error('Error cargando detalles del registro del avatar:', error);
        } finally {
            if (loadToken === this._loadToken) {
                this.details.loading = false;
                this.details.ready = true;
            }
        }
    }

    _getRelationIdFromProps(props) {
        const value = props.record.data[props.name];
        return value ? value[0] : null;
    }

    async _resolveEmployeeId(relationId) {
        if (!relationId) {
            return null;
        }
        const fieldInfo = this.props.record.fields?.[this.props.name];
        const relationModel = fieldInfo ? fieldInfo.relation : null;
        if (!relationModel || relationModel === this.avatarOptions.employeeModel) {
            return relationId;
        }
        const employeeField = this.avatarOptions.relationEmployeeField;
        if (!employeeField) {
            return relationId;
        }
        try {
            const readContext = { ...(this.context || {}) };
            const [relationData] = await this.orm.searchRead(
                relationModel,
                [["id", "=", relationId]],
                [employeeField],
                { context: readContext, limit: 1 }
            );
            if (!relationData) {
                return null;
            }
            const employeeValue = relationData[employeeField];
            if (Array.isArray(employeeValue)) {
                return employeeValue[0] || null;
            }
            return employeeValue || null;
        } catch (error) {
            console.error('Error resolviendo el empleado relacionado:', error);
            return null;
        }
    }

    get avatarSrc() {
        const employee = this.details.employee;
        if (!employee || !employee.id) {
            return '';
        }
        if (employee.gender === 'female') {
            return '/utils/static/src/img/female.png';
        }
        if (employee.gender === 'male') {
            return '/utils/static/src/img/male.png';
        }
        if (employee.has_image) {
            return `/web/image/hr.employee/${employee.id}/image_128`;
        }
        return '';
    }

    async ensureAvatarChannel(channelName) {
        if (this._connectedChannel === channelName) {
            return;
        }
        this._disconnectAvatarChannel();
        if (!channelName) {
            this.startFallbackPolling();
            return;
        }
        try {
            await this.busService.addChannel(channelName);
            this._connectedChannel = channelName;
            this.stopFallbackPolling();
        } catch (error) {
            console.error("Error suscribiendo al canal de avatar:", error);
            this.startFallbackPolling();
        }
    }

    _disconnectAvatarChannel() {
        if (this._connectedChannel) {
            this.busService.deleteChannel(this._connectedChannel);
            this._connectedChannel = null;
        }
    }

    startFallbackPolling() {
        if (this._fallbackInterval || !this._currentRecordId) {
            return;
        }
        const poll = () => {
            if (document.hidden) return;
            this.refreshFromServer();
        };
        poll();
        this._fallbackInterval = setInterval(poll, this.fallbackDelay);
    }

    stopFallbackPolling() {
        if (this._fallbackInterval) {
            clearInterval(this._fallbackInterval);
            this._fallbackInterval = null;
        }
    }

    async refreshFromServer() {
        if (!this._currentRecordId) {
            return;
        }
        try {
            await this._loadWidgetConfig(this._currentRecordId);
            if (this.avatarOptions.channelName !== this._currentChannelName) {
                this._currentChannelName = this.avatarOptions.channelName;
                await this.ensureAvatarChannel(this._currentChannelName);
            }
            await this._loadEmployee(this._currentRelationId);
        } catch (error) {
            console.error("Error refrescando información del avatar:", error);
        }
    }

    async onAvatarNotification(payload) {
        const recordId = this._currentRecordId;
        if (!payload || !recordId) {
            return;
        }
        const payloadRecordId = payload[this.avatarOptions.payloadKey];
        if (payloadRecordId !== recordId) {
            return;
        }
        await this.refreshFromServer();
    }

    async _loadWidgetConfig(recordId) {
        const baseConfig = {
            notificationType: DEFAULT_NOTIFICATION_TYPE,
            payloadKey: DEFAULT_PAYLOAD_KEY,
            employeeModel: DEFAULT_EMPLOYEE_MODEL,
            relationEmployeeField: null,
            fallbackDelay: DEFAULT_FALLBACK_DELAY,
            channelName: null,
        };
        let config = {};
        try {
            const response = await this.orm.call(
                this.props.record.resModel,
                "get_avatar_widget_config",
                [],
                { record_id: recordId, field_name: this.props.name }
            );
            if (response && typeof response === "object") {
                config = normalizeConfigKeys(response);
            }
        } catch (error) {
            console.error("Error obteniendo la configuración del widget de avatar:", error);
        }
        this.avatarOptions = {
            ...baseConfig,
            ...config,
        };
        this.fallbackDelay = this.avatarOptions.fallbackDelay || DEFAULT_FALLBACK_DELAY;
        this._currentChannelName = this.avatarOptions.channelName || null;
        this._updateNotificationSubscription();
    }

    _updateNotificationSubscription() {
        if (!this.busService) {
            return;
        }
        if (this._subscribedNotificationType === this.avatarOptions.notificationType) {
            return;
        }
        if (this._subscribedNotificationType) {
            this.busService.unsubscribe(
                this._subscribedNotificationType,
                this._handleAvatarNotification
            );
        }
        this.busService.subscribe(
            this.avatarOptions.notificationType,
            this._handleAvatarNotification
        );
        this._subscribedNotificationType = this.avatarOptions.notificationType;
    }
}

registry.category("fields").add("ExpAvatarPopup", {
    ...many2OneField,
    component: ExpAvatarPopup,
    displayName: "Datos personales (Empleado)",
});
