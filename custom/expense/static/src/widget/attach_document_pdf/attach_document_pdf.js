/** @odoo-module **/

import { AttachDocumentWidget, attachDocumentWidget } from "@web/views/widgets/attach_document/attach_document";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Extiende AttachDocumentWidget para manejar el valor de retorno del método Python.
 * Si el backend devuelve una acción (ej. notificación de error), la ejecuta.
 * Si no, recarga el registro normalmente.
 */
export class AttachDocumentPdfWidget extends AttachDocumentWidget {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async onFileUploaded(files) {
        const { action, record } = this.props;
        if (!action) {
            return;
        }
        const { resId, resModel } = record;
        const result = await this.env.services.orm.call(resModel, action, [resId], {
            attachment_ids: files.map((file) => file.id),
        });
        if (result && result.type) {
            await this.actionService.doAction(result);
        } else {
            await record.load();
        }
    }
}

registry.category("view_widgets").add("attach_document_pdf", {
    ...attachDocumentWidget,
    component: AttachDocumentPdfWidget,
});
