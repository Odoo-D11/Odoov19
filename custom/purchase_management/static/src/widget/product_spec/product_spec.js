/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { registry } from "@web/core/registry";

export class ProductSpecificationListRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.titleField = "name";
    }

    isSectionOrNote(record) {
        return record?.data?.display_type === 'line_note';
    }

    getRowClass(record) {
        const classes = super.getRowClass(record);
        return this.isSectionOrNote(record) ? `${classes} o_is_line_note` : classes;
    }

    getCellClass(column, record) {
        const classes = super.getCellClass(column, record);
        if (this.isSectionOrNote(record) && column.name !== this.titleField) {
            return `${classes} o_hidden`;
        }
        return classes;
    }

    getColumns(record) {
        const columns = super.getColumns(record);
        if (this.isSectionOrNote(record)) {
            const titleCol = columns.find(c => c.name === this.titleField);
            if (titleCol) {
                return [{
                    ...titleCol,
                    colspan: columns.length
                }];
            }
        }
        return columns;
    }

    /**
     * Override: en el diálogo todos los registros nuevos son simultáneamente
     * isInEdition (porque !resId). leaveEditMode() solo procesa uno por llamada
     * y retorna false si quedan más, lo que bloquea la eliminación.
     * Solución: iterar hasta dejar un único editedRecord (o ninguno).
     */
    async onDeleteRecord(record) {
        this.keepColumnWidths = true;
        let prevEdited = null;
        while (this.props.list.editedRecord && this.props.list.editedRecord !== record) {
            const currentEdited = this.props.list.editedRecord;
            if (currentEdited === prevEdited) return; // stuck: validación impide salir
            prevEdited = currentEdited;
            await this.props.list.leaveEditMode();
        }
        if (this.props.list.editedRecord && this.props.list.editedRecord !== record) {
            return;
        }
        if (this.activeActions.onDelete) {
            this.activeActions.onDelete(record);
        }
    }
}

export class ProductSpecificationOne2Many extends X2ManyField {
    static components = {
        ...X2ManyField.components,
        ListRenderer: ProductSpecificationListRenderer,
    };

    setup() {
        super.setup();

        // Ordenar registros iniciales por secuencia
        this.sortRecordsBySequence();

        // Hook para interceptar la creación de nuevos registros
        const originalAddNewRecord = this.list.addNewRecord.bind(this.list);
        this.list.addNewRecord = async (params) => {
            // Llamar al método original primero para crear el registro
            const result = await originalAddNewRecord(params);

            // Después de crear, renumerar toda la lista
            await this.resequenceAllRecords();

            return result;
        };
    }

    sortRecordsBySequence() {
        if (this.list && this.list.records && this.list.records.length > 1) {
            this.list.records.sort((a, b) => {
                const seqA = a.data.sequence || 9999;
                const seqB = b.data.sequence || 9999;
                return seqA - seqB;
            });
        }
    }

    async resequenceAllRecords() {
        const records = this.list.records || [];

        // Asignar secuencias 1, 2, 3, 4... en el orden actual de la lista
        for (let i = 0; i < records.length; i++) {
            const newSeq = i + 1;
            if (records[i].data.sequence !== newSeq) {
                await records[i].update({ sequence: newSeq }, { save: false });
            }
        }
    }
}

export const productSpecificationOne2Many = {
    ...x2ManyField,
    component: ProductSpecificationOne2Many,
};

registry.category("fields").add("product_specification_one2many", productSpecificationOne2Many);
