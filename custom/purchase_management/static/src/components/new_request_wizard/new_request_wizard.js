/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const DEBOUNCE = 300;

export class NewRequestWizardDialog extends Component {
    static template = "purchase_management.NewRequestWizardDialog";
    static components = { Dialog };
    static props = {
        onConfirm: Function,
        close: { type: Function, optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");

        this._defaultUomId   = null;
        this._defaultUomName = "";

        this.state = useState({
            step: 1,
            transitioning: false,

            // ── Step 1: Información ──────────────────────────────────────────
            subject: "",
            typeId: null, typeName: "", typeSearch: "",
            typeDropdownOpen: false, typeItems: [], typeDropdownStyle: null,

            projectId: null, projectName: "", projectSearch: "",
            projectDropdownOpen: false, projectItems: [], projectDropdownStyle: null,

            reason: "",

            // ── Step 2: Productos (manual) ───────────────────────────────────
            products: [this._newProduct(1)],
            nextProductId: 2,

            // ── Step 2: Importar (Excel) ─────────────────────────────────────
            wizardMode: "manual",          // 'manual' | 'excel'
            importStep: "instructions",    // 'instructions' | 'main'
            importTemplateDownloaded: false,
            importUploading: false,
            importResults: null,           // null | { rows: [...], errors: [...] }

            // ── Step 3: Fecha ────────────────────────────────────────────────
            deadline: "",

            // ── UI ───────────────────────────────────────────────────────────
            errors: {},
            submitting: false,
        });

        this._typeTimer    = null;
        this._projectTimer = null;
        this._uomTimers    = {};

        onWillStart(async () => {
            const found = await this.orm.searchRead(
                "warehouse.uom", [["name", "=", "Unidad"]], ["id", "name"], { limit: 1 }
            );
            if (found.length) {
                this._defaultUomId   = found[0].id;
                this._defaultUomName = found[0].name;
                const p = this.state.products[0];
                p.uomId = found[0].id; p.uomName = found[0].name; p.uomSearch = found[0].name;
            }
        });
    }

    _newProduct(id) {
        return {
            id, name: "", qty: 1,
            uomId:    this._defaultUomId,
            uomName:  this._defaultUomName,
            uomSearch: this._defaultUomName,
            uomDropdownOpen: false, uomItems: [],
            uomDropdownStyle: null,
        };
    }

    /** Calcula style position:fixed para el dropdown escapando overflow del Dialog 
     *  y decide si mostrarlo arriba o abajo según el espacio disponible.
     */
    _calcDropdownStyle(inputEl) {
        const r = inputEl.getBoundingClientRect();
        const dropdownHeight = 220; // Coincide con max-height en SCSS
        const margin = 4;
        
        // Determinar si hay espacio abajo o si es mejor mostrarlo arriba
        const spaceBelow = window.innerHeight - r.bottom;
        const showAbove = spaceBelow < (dropdownHeight + margin) && r.top > (dropdownHeight + margin);

        return {
            position: 'fixed',
            left:   `${r.left}px`,
            width:  `${r.width}px`,
            top:    showAbove ? 'auto' : `${r.bottom + margin}px`,
            bottom: showAbove ? `${window.innerHeight - r.top + margin}px` : 'auto',
            maxHeight: `${dropdownHeight}px`,
            overflowY: 'auto',
            zIndex: 5000,
            background: 'white',
            boxSizing: 'border-box',
        };
    }

    // ── NAVIGATION ───────────────────────────────────────────────────────────

    async goNext() {
        if (this.state.transitioning) return;
        if (!this._validateStep(this.state.step)) return;
        this._transition(this.state.step + 1);
    }

    goBack() {
        if (this.state.transitioning) return;
        this._transition(this.state.step - 1);
    }

    _transition(nextStep) {
        this.state.transitioning = true;
        setTimeout(() => {
            this.state.step   = nextStep;
            this.state.errors = {};
            this.state.transitioning = false;
        }, 160);
    }

    // ── VALIDATION ───────────────────────────────────────────────────────────

    _validateStep(step) {
        const errors = {};
        if (step === 1) {
            if (!this.state.typeId)         errors.typeId    = "Seleccione el tipo de SDC";
            if (!this.state.subject.trim()) errors.subject   = "El asunto es obligatorio";
            if (!this.state.projectId)      errors.projectId = "Seleccione un proyecto";
            if (!this.state.reason.trim())  errors.reason    = "El motivo es obligatorio";
        }
        if (step === 2 && this.state.wizardMode === "manual") {
            for (const p of this.state.products) {
                if (!p.name.trim())        errors[`pn_${p.id}`] = true;
                if (!p.qty || p.qty <= 0)  errors[`pq_${p.id}`] = true;
                if (!p.uomId)              errors[`pu_${p.id}`] = true;
            }
        }
        if (step === 3) {
            if (!this.state.deadline) errors.deadline = "La fecha límite es obligatoria";
        }
        this.state.errors = errors;
        return Object.keys(errors).length === 0;
    }

    // ── CONFIRM / CANCEL ─────────────────────────────────────────────────────

    async onConfirm() {
        if (this.state.submitting) return;
        if (!this._validateStep(3)) return;
        this.state.submitting = true;
        try {
            const productCommands = this.state.products.map(p => [0, 0, {
                name: p.name, qty: p.qty, uom_id: p.uomId,
            }]);
            const [id] = await this.orm.create("request.quotation", [{
                subject:          this.state.subject,
                type_id:          this.state.typeId,
                project_id:       this.state.projectId,
                reason:           this.state.reason,
                deadline:         this.state.deadline,
                product_line_ids: productCommands,
            }]);
            this._close();
            await this.props.onConfirm(id);
        } catch (e) {
            this.notification.add(
                e?.data?.message || "Error al crear la solicitud. Intente de nuevo.",
                { type: "danger" }
            );
            this.state.submitting = false;
        }
    }

    onCancel() {
        if (this.state.submitting) return;
        this._close();
    }

    _close() {
        if (this.props.close) this.props.close();
    }

    // ── MODE TOGGLE ──────────────────────────────────────────────────────────

    onSetManualMode() {
        if (this.state.wizardMode === "manual") return;
        this.state.wizardMode = "manual";
        this._resetImportState();
        // Si step 1 nunca fue completado, volver al inicio
        if (this.state.step === 2 && !this._isStep1Complete()) {
            this.state.step = 1;
        }
    }

    onSetExcelMode() {
        if (this.state.wizardMode === "excel") return;
        this.state.wizardMode = "excel";
        // Ir directo al panel de importación (step 2)
        this.state.step = 2;
        this.state.errors = {};
    }

    _isStep1Complete() {
        return !!(
            this.state.typeId &&
            this.state.subject.trim() &&
            this.state.projectId &&
            this.state.reason.trim()
        );
    }

    _resetImportState() {
        this.state.importStep               = "instructions";
        this.state.importResults            = null;
        this.state.importTemplateDownloaded = false;
        this.state.importUploading          = false;
    }

    // ── IMPORT FLOW NAVIGATION ────────────────────────────────────────────────

    onGoToExcelInstructions() {
        this.state.importStep    = "instructions";
        this.state.importResults = null;
    }

    onGoToExcelMain() {
        this.state.importStep = "main";
    }

    onResetImport() {
        this.state.importResults = null;
    }

    onApplyImport() {
        const data = this.state.importResults;
        if (!data) return;

        // Poblar cabecera
        const h = data.header || {};
        this.state.typeId       = h.typeId    || null;
        this.state.typeName     = h.typeName  || "";
        this.state.typeSearch   = h.typeName  || "";
        this.state.projectId    = h.projectId   || null;
        this.state.projectName  = h.projectName || "";
        this.state.projectSearch = h.projectName || "";
        this.state.subject  = h.subject  || "";
        this.state.reason   = h.reason   || "";
        this.state.deadline = h.deadline || "";

        // Poblar productos
        let nextId = this.state.nextProductId;
        this.state.products = (data.rows || []).map(row => ({
            id: nextId++,
            name: row.name,
            qty:  row.qty,
            uomId:    row.uomId,
            uomName:  row.uomName,
            uomSearch: row.uomName,
            uomDropdownOpen: false,
            uomItems: [],
        }));
        this.state.nextProductId = nextId;

        // Ir a step 3 (resumen + confirmar) con todos los datos cargados
        this.state.wizardMode = "manual";
        this._resetImportState();
        this.state.step   = 3;
        this.state.errors = {};
    }

    // ── TEMPLATE DOWNLOAD ─────────────────────────────────────────────────────

    async onDownloadTemplate() {
        try {
            const resp = await fetch("/purchase_management/nrw_download_template", { method: "GET" });
            const data = await resp.json();
            if (data.url) {
                window.open(data.url, "_blank");
                this.state.importTemplateDownloaded = true;
            } else {
                this.notification.add(data.error || "Error al generar plantilla", { type: "danger" });
            }
        } catch (e) {
            this.notification.add("Error al descargar la plantilla", { type: "danger" });
        }
    }

    // ── EXCEL UPLOAD ──────────────────────────────────────────────────────────

    async onImportExcel(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        ev.target.value = "";   // permite re-subir el mismo archivo

        this.state.importUploading = true;
        this.state.importResults   = null;

        try {
            const formData = new FormData();
            formData.append("file", file);

            const resp = await fetch("/purchase_management/nrw_upload_products", {
                method: "POST",
                body: formData,
            });
            const data = await resp.json();

            if (data.error) {
                this.notification.add(data.error, { type: "danger" });
            } else {
                this.state.importResults = data;
            }
        } catch (e) {
            this.notification.add("Error al procesar el archivo.", { type: "danger" });
        }

        this.state.importUploading = false;
    }

    // ── TYPE M2O ─────────────────────────────────────────────────────────────

    onTypeFocus(ev) {
        this.state.typeDropdownStyle = this._calcDropdownStyle(ev.target);
        this.state.typeDropdownOpen = true;
        if (!this.state.typeItems.length) this._searchType(this.state.typeSearch);
    }
    onTypeInput(ev) {
        this.state.typeSearch = ev.target.value;
        this.state.typeId     = null; this.state.typeName = "";
        this.state.typeDropdownOpen = true;
        clearTimeout(this._typeTimer);
        this._typeTimer = setTimeout(() => this._searchType(ev.target.value), DEBOUNCE);
    }
    async _searchType(term) {
        const res = await this.orm.call("request.type", "name_search", [term], { limit: 10 });
        this.state.typeItems = res.map(([id, name]) => ({ id, name }));
    }
    selectType(id, name) {
        this.state.typeId = id; this.state.typeName = name;
        this.state.typeSearch = name; this.state.typeDropdownOpen = false;
        delete this.state.errors.typeId;
    }
    onTypeBlur() { setTimeout(() => { this.state.typeDropdownOpen = false; }, 200); }

    // ── PROJECT M2O ──────────────────────────────────────────────────────────

    onProjectFocus(ev) {
        this.state.projectDropdownStyle = this._calcDropdownStyle(ev.target);
        this.state.projectDropdownOpen = true;
        if (!this.state.projectItems.length) this._searchProject(this.state.projectSearch);
    }
    onProjectInput(ev) {
        this.state.projectSearch = ev.target.value;
        this.state.projectId = null; this.state.projectName = "";
        this.state.projectDropdownOpen = true;
        clearTimeout(this._projectTimer);
        this._projectTimer = setTimeout(() => this._searchProject(ev.target.value), DEBOUNCE);
    }
    async _searchProject(term) {
        const res = await this.orm.call("project.management", "name_search", [term], { limit: 10 });
        this.state.projectItems = res.map(([id, name]) => ({ id, name }));
    }
    selectProject(id, name) {
        this.state.projectId = id; this.state.projectName = name;
        this.state.projectSearch = name; this.state.projectDropdownOpen = false;
        delete this.state.errors.projectId;
    }
    onProjectBlur() { setTimeout(() => { this.state.projectDropdownOpen = false; }, 200); }

    // ── PRODUCT TABLE ─────────────────────────────────────────────────────────

    addProduct() {
        this.state.products.push(this._newProduct(this.state.nextProductId++));
    }
    removeProduct(id) {
        if (this.state.products.length <= 1) return;
        const idx = this.state.products.findIndex(p => p.id === id);
        if (idx !== -1) this.state.products.splice(idx, 1);
    }
    onProductNameChange(id, ev) {
        const p = this.state.products.find(p => p.id === id);
        if (p) { p.name = ev.target.value; delete this.state.errors[`pn_${id}`]; }
    }
    onProductQtyChange(id, ev) {
        const p = this.state.products.find(p => p.id === id);
        if (p) { p.qty = parseFloat(ev.target.value) || 0; delete this.state.errors[`pq_${id}`]; }
    }
    onUomFocus(productId, ev) {
        const p = this.state.products.find(p => p.id === productId);
        if (!p) return;
        if (ev?.target) p.uomDropdownStyle = this._calcDropdownStyle(ev.target);
        p.uomDropdownOpen = true;
        if (!p.uomItems.length) this._searchUom(productId, p.uomSearch);
    }
    onUomInput(productId, ev) {
        const p = this.state.products.find(p => p.id === productId);
        if (!p) return;
        p.uomSearch = ev.target.value; p.uomId = null; p.uomName = ""; p.uomDropdownOpen = true;
        clearTimeout(this._uomTimers[productId]);
        this._uomTimers[productId] = setTimeout(() => this._searchUom(productId, ev.target.value), DEBOUNCE);
    }
    async _searchUom(productId, term) {
        const p = this.state.products.find(p => p.id === productId);
        if (!p) return;
        const res = await this.orm.call("warehouse.uom", "name_search", [term], { limit: 10 });
        p.uomItems = res.map(([id, name]) => ({ id, name }));
    }
    selectUom(productId, id, name) {
        const p = this.state.products.find(p => p.id === productId);
        if (!p) return;
        p.uomId = id; p.uomName = name; p.uomSearch = name; p.uomDropdownOpen = false;
        delete this.state.errors[`pu_${productId}`];
    }
    onUomBlur(productId) {
        setTimeout(() => {
            const p = this.state.products.find(p => p.id === productId);
            if (p) p.uomDropdownOpen = false;
        }, 200);
    }

    // ── INLINE FIELD HANDLERS ────────────────────────────────────────────────

    onSubjectInput(ev)  { this.state.subject  = ev.target.value; delete this.state.errors.subject; }
    onReasonInput(ev)   { this.state.reason   = ev.target.value; delete this.state.errors.reason; }
    onDeadlineChange(ev){ this.state.deadline = ev.target.value; delete this.state.errors.deadline; }

    // ── COMPUTED ──────────────────────────────────────────────────────────────

    get isLastStep()        { return this.state.step === 3; }
    get isFirstStep()       { return this.state.step === 1; }
    get totalProducts()     { return this.state.products.length; }
    get inExcelFlow()       { return this.state.wizardMode === "excel" && this.state.step === 2; }
    get importErrorCount()  { return this.state.importResults?.errors?.length ?? 0; }
    get importSuccessCount(){ return this.state.importResults?.rows?.length ?? 0; }
}
