/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount, onWillUpdateProps, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

const MAX_SIZE_BYTES = 10 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set(['.pdf', '.doc', '.docx']);

function _filterValidFiles(files, notification) {
    const valid = [];
    for (const file of files) {
        const ext = "." + file.name.split(".").pop().toLowerCase();
        if (!ALLOWED_EXTENSIONS.has(ext)) {
            notification.add(
                _t("%s: solo se permiten archivos PDF o Word (.pdf, .doc, .docx).", file.name),
                { type: "warning" }
            );
            continue;
        }
        if (file.size > MAX_SIZE_BYTES) {
            notification.add(
                _t("%s: supera el límite de 10 MB.", file.name),
                { type: "warning" }
            );
            continue;
        }
        valid.push(file);
    }
    return valid;
}

async function _uploadFiles(http, rfqId, validFiles) {
    const formData = new FormData();
    formData.append("csrf_token", odoo.csrf_token);
    formData.append("rfq_id", String(rfqId));
    for (const file of validFiles) {
        formData.append("ufile", file);
    }
    const responseText = await http.post(
        "/purchase_management/attach_technical_spec",
        formData,
        "text"
    );
    return JSON.parse(responseText);
}

// ---------------------------------------------------------------------------
// Dialog: gestión de fichas técnicas en tarjetas Kanban
// ---------------------------------------------------------------------------

class TechnicalSpecDialog extends Component {
    static template = "purchase_management.TechnicalSpecDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        rfqId: Number,
        initialAttachments: Array,
        onAttachmentsChange: Function,
        isDraft: Boolean,
    };

    setup() {
        // Captura de servicios como propiedades de instancia
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.http = useService("http");
        this._fileInput = null;

        this.state = useState({
            attachments: [...this.props.initialAttachments],
            uploading: false,
        });

        onMounted(() => {
            this._fileInput = document.createElement("input");
            this._fileInput.type = "file";
            this._fileInput.accept = ".pdf,.doc,.docx";
            this._fileInput.multiple = true;
            this._fileInput.style.display = "none";
            this._fileInput.addEventListener("change", (ev) => this._onFilesSelected(ev));
            document.body.appendChild(this._fileInput);
        });

        onWillUnmount(() => {
            if (this._fileInput) {
                this._fileInput.remove();
                this._fileInput = null;
            }
        });
    }

    getFileType(name) {
        return (name || '').split('.').pop().toUpperCase() || 'FILE';
    }

    getFileClass(name) {
        const ext = (name || '').split('.').pop().toLowerCase();
        return ext === 'pdf' ? 'o_spec_type_pdf' : 'o_spec_type_doc';
    }

    openAttachment(id) {
        window.open(`/web/content/${id}?download=false`, '_blank');
    }

    async deleteAttachment(id) {
        // Captura local antes del await para evitar pérdida de contexto
        const orm = this.orm;
        const notification = this.notification;
        const onAttachmentsChange = this.props.onAttachmentsChange;
        const rfqId = this.props.rfqId;

        try {
            await orm.write('request.quotation', [rfqId], {
                technical_spec_attachment_ids: [[3, id]],
            });
            this.state.attachments = this.state.attachments.filter(a => a.id !== id);
            onAttachmentsChange(this.state.attachments);
        } catch {
            notification.add(
                _t("Error al eliminar el archivo. Por favor, inténtelo de nuevo."),
                { type: "danger" }
            );
        }
    }

    openFilePicker() {
        if (this._fileInput) {
            this._fileInput.value = "";
            this._fileInput.click();
        }
    }

    async _onFilesSelected(ev) {
        const files = [...ev.target.files];
        if (!files.length) return;

        const notification = this.notification;
        const validFiles = _filterValidFiles(files, notification);
        if (!validFiles.length) return;

        this.state.uploading = true;
        try {
            const data = await _uploadFiles(this.http, this.props.rfqId, validFiles);
            if (data.error) {
                notification.add(data.error, { type: "danger", sticky: true });
                return;
            }
            for (const warn of (data.warnings || [])) {
                notification.add(warn, { type: "warning" });
            }
            const newAttachments = (data.attachments || []).map(a => ({ id: a.id, name: a.name }));
            if (newAttachments.length > 0) {
                this.state.attachments = [...this.state.attachments, ...newAttachments];
                this.props.onAttachmentsChange(this.state.attachments);
                notification.add(
                    _t("%s ficha(s) técnica(s) adjuntada(s) correctamente.", newAttachments.length),
                    { type: "success" }
                );
            }
        } catch {
            notification.add(
                _t("Error al subir los archivos. Por favor, inténtelo de nuevo."),
                { type: "danger", sticky: true }
            );
        } finally {
            this.state.uploading = false;
        }
    }
}

// ---------------------------------------------------------------------------
// Widget del encabezado del formulario
// ---------------------------------------------------------------------------

class AttachTechnicalSpecLauncher extends Component {
    static template = "purchase_management.AttachTechnicalSpecLauncher";
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.http = useService("http");
        this.orm = useService("orm");
        this.dialogService = useService("dialog");
        this._fileInput = null;

        this.state = useState({ attachments: [] });

        onWillStart(async () => {
            await this._syncAttachments(this.props.record);
        });

        onWillUpdateProps(async (nextProps) => {
            await this._syncAttachments(nextProps.record);
        });

        onMounted(() => {
            this._fileInput = document.createElement("input");
            this._fileInput.type = "file";
            this._fileInput.accept = ".pdf,.doc,.docx";
            this._fileInput.multiple = true;
            this._fileInput.style.display = "none";
            this._fileInput.addEventListener("change", (ev) => this._onFilesSelected(ev));
            document.body.appendChild(this._fileInput);
        });

        onWillUnmount(() => {
            if (this._fileInput) {
                this._fileInput.remove();
                this._fileInput = null;
            }
        });
    }

    async _syncAttachments(record) {
        const field = record.data.technical_spec_attachment_ids;
        const ids = field?.currentIds || field?.records?.map(r => r.resId) || [];

        if (!ids.length) {
            this.state.attachments = [];
            return;
        }

        // Evita re-fetch si los IDs no cambiaron
        const currentIds = this.state.attachments.map(a => a.id);
        const same = ids.length === currentIds.length && ids.every(id => currentIds.includes(id));
        if (same) return;

        const data = await this.orm.read('ir.attachment', ids, ['name']);
        this.state.attachments = data.map(a => ({ id: a.id, name: a.name }));
    }

    get hasAttachments() {
        return this.state.attachments.length > 0;
    }

    openFilePicker() {
        if (this._fileInput) {
            this._fileInput.value = "";
            this._fileInput.click();
        }
    }

    openDialog() {
        this.dialogService.add(TechnicalSpecDialog, {
            rfqId: this.props.record.resId,
            initialAttachments: this.state.attachments,
            isDraft: this.props.record.data.state === 'draft',
            onAttachmentsChange: (attachments) => {
                this.state.attachments = attachments;
            },
        });
    }

    async _onFilesSelected(ev) {
        const files = [...ev.target.files];
        if (!files.length) return;

        const notification = this.notification;
        const validFiles = _filterValidFiles(files, notification);
        if (!validFiles.length) return;

        const rfqId = this.props.record.resId;
        try {
            const data = await _uploadFiles(this.http, rfqId, validFiles);
            if (data.error) {
                notification.add(data.error, { type: "danger", sticky: true });
                return;
            }
            for (const warn of (data.warnings || [])) {
                notification.add(warn, { type: "warning" });
            }
            const newAttachments = (data.attachments || []).map(a => ({ id: a.id, name: a.name }));
            if (newAttachments.length > 0) {
                this.state.attachments = [...this.state.attachments, ...newAttachments];
                notification.add(
                    _t("%s ficha(s) técnica(s) adjuntada(s) correctamente.", newAttachments.length),
                    { type: "success" }
                );
            }
        } catch {
            notification.add(
                _t("Error al subir los archivos. Por favor, inténtelo de nuevo."),
                { type: "danger", sticky: true }
            );
        }
    }
}

registry.category("view_widgets").add("spec_launcher", {
    component: AttachTechnicalSpecLauncher,
});
