/** @odoo-module **/

import { Component, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useAutoresize } from "@web/core/utils/autoresize";
import { useInputField } from "@web/views/fields/input_field_hook";

export class ProductNameWidget extends Component {
    static template = "purchase_management.ProductNameWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.textareaRef = useRef("textarea");
        this.inputRef = useRef("input");

        // Determinar si es nota o producto
        const isNote = this.props.record.data.display_type === 'line_note';

        useInputField({
            getValue: () => this.props.record.data[this.props.name] || "",
            refName: isNote ? "textarea" : "input",
            preventLineBreaks: !isNote, 
        });

        if (isNote) {
            useAutoresize(this.textareaRef, { minimumHeight: 0 });
        }

        if (!isNote) {
            this.previousName = this.props.record.data.name;
        }
    }

    async onInput(ev) {
        const newName = ev.target.value;
        // Solo para productos
        if (!this.props.record.data.display_type && this.previousName !== newName) {
            if (this.previousName) {
                await this.updateRelatedNotes(this.previousName, newName);
            }
            this.previousName = newName;
        }
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    get showButton() {
        // Mostrar botón siempre que NO sea una nota
        return !this.props.record.data.display_type;
    }

    get hasSpecification() {
        const model = this.props.record.model;
        const records = model.records;
        if (!records) return false;

        const currentIndex = records.findIndex(r => r === this.props.record);

        // Verificar si la siguiente línea es una nota
        if (currentIndex < records.length - 1) {
            const nextRecord = records[currentIndex + 1];
            return nextRecord.data.display_type === 'line_note';
        }

        return false;
    }

    get buttonIcon() {
        return this.hasSpecification ? "fa fa-align-justify" : "fa fa-align-justify";
    }

    get buttonClass() {
        return "text-dark"; // Siempre negro
    }

    get buttonTitle() {
        return this.hasSpecification ? "Ver especificación" : "Agregar especificación";
    }

    async onButtonClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        // Leer desde el DOM si aún no se ha sincronizado con record.data (race condition blur/click)
        const domValue = this.inputRef.el?.value?.trim() || '';
        const recordValue = this.value.trim();
        const currentValue = recordValue || domValue;

        if (!currentValue) {
            this.notification.add(_t("Ingrese el nombre del producto primero."), { type: "warning" });
            return;
        }

        // Sincronizar el valor del DOM al record antes de crear la especificación
        if (!recordValue && domValue) {
            await this.props.record.update({ [this.props.name]: domValue });
        }

        // Si ya tiene especificación, enfocar en ella
        if (this.hasSpecification) {
            const model = this.props.record.model;
            const currentSequence = this.props.record.data.sequence || 10;
            const noteRecord = model.records.find(r =>
                r.data.display_type === 'line_note' &&
                r.data.sequence === currentSequence + 1
            );
            if (noteRecord && model.enterEditMode) {
                await model.enterEditMode(noteRecord);
            }
            return;
        }

        // Crear nueva especificación
        await this.createSpecification();
    }

    async createSpecification() {
        try {
            const currentRecord = this.props.record;
            const currentSequence = currentRecord.data.sequence || 1;

            let requestQuotationId = null;
            if (currentRecord.data.request_quotation_id) {
                const m2o = currentRecord.data.request_quotation_id;
                requestQuotationId = m2o?.id ?? (Array.isArray(m2o) ? m2o[0] : null);
            }

            const parentRecord = currentRecord.model.root;
            const productLineField = parentRecord.data.product_line_ids;

            if (!productLineField) {
                console.error("No se pudo acceder al campo de líneas de producto");
                throw new Error("No se pudo acceder al campo de líneas de producto");
            }

            const allRecords = productLineField.records;
            const currentIndex = allRecords.findIndex(r => r === currentRecord);

            let lastNoteIndex = currentIndex;
            for (let i = currentIndex + 1; i < allRecords.length; i++) {
                if (allRecords[i].data.display_type === 'line_note') {
                    lastNoteIndex = i;
                } else {
                    break;
                }
            }

            const targetIndex = lastNoteIndex + 1;

            console.log("Creando nota después del índice:", lastNoteIndex, "en posición:", targetIndex);

            const newRecordContext = {
                default_display_type: 'line_note',
                default_product_name: currentRecord.data.name,
            };
            if (requestQuotationId) {
                newRecordContext.default_request_quotation_id = requestQuotationId;
            }

            // Crear el nuevo registro SIN secuencia, dejamos que se cree al final
            const newRecord = await productLineField.addNewRecord({
                context: newRecordContext,
                mode: 'edit'
            });

            if (!newRecord) {
                console.error("Fallo al crear el registro de especificación");
                throw new Error("No se pudo crear el registro de especificación");
            }

            // Mover la nota a su posición correcta en la lista
            const currentNewIndex = productLineField.records.findIndex(r => r === newRecord);
            console.log("Nota creada en posición:", currentNewIndex, "debe ir en:", targetIndex);

            if (currentNewIndex !== targetIndex) {
                // Remover del final donde se creó
                const [movedRecord] = productLineField.records.splice(currentNewIndex, 1);
                // Insertar en la posición correcta (después de las notas del producto)
                productLineField.records.splice(targetIndex, 0, movedRecord);
                console.log("Nota movida de", currentNewIndex, "a", targetIndex);
            }

            // RENUMERAR TODA LA LISTA después de mover
            await this.resequenceAll();

        } catch (error) {
            console.error("Error al crear especificación:", error);
            console.error("Stack trace:", error.stack);
            console.error("Datos del registro actual:", this.props.record?.data);
            this.notification.add(_t("Error al crear especificación: ") + error.message, { type: "danger" });
        }
    }

    async updateRelatedNotes(oldName, newName) {
        try {
            const parentRecord = this.props.record.model.root;
            const productLineField = parentRecord.data.product_line_ids;
            const allRecords = productLineField.records;

            // Solo actualizar la nota inmediatamente después de este producto
            const currentIndex = allRecords.findIndex(r => r === this.props.record);
            if (currentIndex >= 0 && currentIndex + 1 < allRecords.length) {
                const nextRecord = allRecords[currentIndex + 1];
                if (nextRecord.data.display_type === 'line_note' &&
                    (nextRecord.data.product_name || '').trim().toLowerCase() === (oldName || '').trim().toLowerCase()) {
                    await nextRecord.update({ product_name: newName }, { save: false });
                }
            }

            console.log(`Nota actualizada de "${oldName}" a "${newName}"`);
        } catch (error) {
            console.error("Error al actualizar notas:", error);
        }
    }

    async resequenceAll() {
        try {
            const parentRecord = this.props.record.model.root;
            const productLineField = parentRecord.data.product_line_ids;
            const allRecords = productLineField.records;

            // Asignar secuencias 1, 2, 3, 4... según el orden visual actual
            for (let i = 0; i < allRecords.length; i++) {
                const newSeq = i + 1;
                if (allRecords[i].data.sequence !== newSeq) {
                    await allRecords[i].update({ sequence: newSeq }, { save: false });
                }
            }

            console.log("Lista renumerada: secuencias 1-" + allRecords.length);
        } catch (error) {
            console.error("Error al renumerar lista:", error);
        }
    }
}

registry.category("fields").add("product_line_name", {
    component: ProductNameWidget,
    supportedTypes: ["char", "text"],
});
