/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { useX2ManyCrud, useOpenX2ManyRecord } from "@web/views/fields/relational_utils";
import { ListRenderer } from "@web/views/list/list_renderer";
import { onMounted, onPatched } from "@odoo/owl";

export class CertificationListRenderer extends ListRenderer {
    static template = "rrhh.CertificationListRenderer";
    static rowsTemplate = "rrhh.CertificationListRenderer.Rows";
    static recordRowTemplate = "rrhh.CertificationListRenderer.RecordRow";
    static useMagicColumnWidths = false;

    setup() {
        super.setup();
        onMounted(() => this._syncTimeline());
        onPatched(() => this._syncTimeline());
    }

    /** Alinea la línea vertical al centro exacto del dot usando offsetLeft medido en DOM */
    _syncTimeline() {
        if (!this.tableRef?.el) return;
        this.tableRef.el.querySelectorAll(".o_cert_timeline_cell").forEach((cell) => {
            const dot = cell.querySelector(".o_cert_dot");
            if (!dot) return;
            const lineLeft = dot.offsetLeft + Math.round(dot.offsetWidth / 2);
            cell.style.setProperty("--cert-line-left", `${lineLeft}px`);
        });
    }

    get isEditable() { return this.props.editable !== false; }
    get showTable() { return this.props.list.records.length > 0; }
    get displayRowCreates() { return false; }

    getRowClass(record) {
        const base = super.getRowClass(record);
        const records = this.props.list.records;
        const isLast = records.length > 0 && records[records.length - 1] === record;
        return isLast ? `${base} o_data_row_last` : base;
    }

    formatCertDate(date, isEnd = false) {
        if (!date) return isEnd ? _t("En curso") : "";
        return date.toFormat("MM/yyyy");
    }

    /** Convierte el valor raw del campo selection en su etiqueta legible */
    getCertLevelLabel(value) {
        if (!value) return "";
        const field = this.props.list.fields["certification_level"];
        if (!field?.selection) return value;
        const option = field.selection.find(([v]) => v === value);
        return option ? option[1] : value;
    }
}

export class CertificationX2ManyField extends X2ManyField {
    static components = { ...X2ManyField.components, ListRenderer: CertificationListRenderer };

    setup() {
        super.setup();
        const { saveRecord, updateRecord } = useX2ManyCrud(() => this.list, this.isMany2Many);
        const openRecord = useOpenX2ManyRecord({
            resModel: this.list.resModel,
            activeField: this.activeField,
            activeActions: this.activeActions,
            getList: () => this.list,
            saveRecord: async (record) => {
                await saveRecord(record);
                await this.props.record.save();
            },
            updateRecord,
            withParentId: this.props.widget !== "many2many",
        });
        this._openRecord = (params) => {
            params.title = _t("Odoo");
            openRecord({ ...params });
        };
    }

    async onAdd({ context, editable } = {}) {
        return super.onAdd({
            editable,
            context: { ...context, default_employee_id: this.props.record.resId },
        });
    }
}

export const certificationX2ManyField = { ...x2ManyField, component: CertificationX2ManyField };
registry.category("fields").add("certification_one2many", certificationX2ManyField);
