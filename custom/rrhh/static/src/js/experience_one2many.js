/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import {
    useX2ManyCrud,
    useOpenX2ManyRecord,
} from "@web/views/fields/relational_utils";
import { ListRenderer } from "@web/views/list/list_renderer";
import { onMounted, onPatched } from "@odoo/owl";

export class ExperienceListRenderer extends ListRenderer {
    static template = "rrhh.ExperienceListRenderer";
    static rowsTemplate = "rrhh.ExperienceListRenderer.Rows";
    static recordRowTemplate = "rrhh.ExperienceListRenderer.RecordRow";
    static useMagicColumnWidths = false;

    setup() {
        super.setup();
        // Después de cada render, alinear la línea exactamente bajo el centro del dot
        onMounted(() => this._syncTimeline());
        onPatched(() => this._syncTimeline());
    }

    /**
     * Lee la posición real del dot tras el render y establece --exp-line-left
     * como CSS custom property en cada celda de timeline.
     * Así la línea ::before siempre queda centrada en el dot, sin importar
     * qué padding apliquen Odoo o Bootstrap sobre el <td>.
     */
    _syncTimeline() {
        if (!this.tableRef?.el) return;
        this.tableRef.el.querySelectorAll(".o_experience_timeline_cell").forEach((cell) => {
            const dot = cell.querySelector(".o_exp_dot");
            if (!dot) return;
            // offsetLeft: posición del dot relativa al td (que es position:relative)
            const lineLeft = dot.offsetLeft + Math.round(dot.offsetWidth / 2);
            cell.style.setProperty("--exp-line-left", `${lineLeft}px`);
        });
    }

    get isEditable() {
        return this.props.editable !== false;
    }

    get showTable() {
        return this.props.list.records.length > 0;
    }

    // Ocultamos el "Agregar una línea" estándar — tenemos el nuestro en el Rows template
    get displayRowCreates() {
        return false;
    }

    /**
     * Marca el último registro con o_data_row_last para que el SCSS
     * pueda cortar la línea vertical exactamente en el centro.
     */
    getRowClass(record) {
        const base = super.getRowClass(record);
        const records = this.props.list.records;
        const isLast = records.length > 0 && records[records.length - 1] === record;
        return isLast ? `${base} o_data_row_last` : base;
    }

    /**
     * Formatea un campo Date (luxon DateTime) como "MM/YYYY".
     * Si isEnd=true y el valor es falso devuelve "Actual".
     */
    formatExperienceDate(date, isEnd = false) {
        if (!date) {
            return isEnd ? _t("Actual") : "";
        }
        return date.toFormat("MM/yyyy");
    }

    /**
     * Extrae el nombre de un campo Many2one de forma segura.
     * En Odoo 18, record.data devuelve el valor como objeto {id, display_name}
     * o como tupla [id, name] dependiendo del contexto, por eso se manejan ambos.
     */
    getCityName(cityValue) {
        if (!cityValue) return "";
        if (Array.isArray(cityValue)) return cityValue[1] || "";
        return cityValue.display_name || "";
    }
}

export class ExperienceX2ManyField extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: ExperienceListRenderer,
    };

    setup() {
        super.setup();

        const { saveRecord, updateRecord } = useX2ManyCrud(
            () => this.list,
            this.isMany2Many
        );

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
            context: {
                ...context,
                default_employee_id: this.props.record.resId,
            },
        });
    }
}

export const experienceX2ManyField = {
    ...x2ManyField,
    component: ExperienceX2ManyField,
};

registry.category("fields").add("experience_one2many", experienceX2ManyField);
