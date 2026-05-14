/** @odoo-module **/

import { Component, onMounted, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

export class ProductLinkingDialog extends Component {
    static template = "purchase_management.ProductLinkingDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        quotationId: Number,
        title: { type: String, optional: true },
        onConfirmSuccess: { type: Function, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.rootRef = useRef("root");

        // Debounce timers per line
        this._debounceTimers = {};
        this._ccDebounceTimers = {};
        this._productSearchTimer = null;


        this.state = useState({
            loading: true,
            error: null,
            reference: "",
            subject: "",
            requestType: "",
            projectId: null,
            lines: [],

            // Wizard — índice del producto actual
            wizardIndex: 0,

            // Modo del wizard: 'manual' | 'excel'
            wizardMode: 'manual',

            // Centro de costo global (aplica a todas las líneas por defecto)
            globalCostCenterId: null,
            globalCostCenterName: '',
            globalCcInputText: '',
            globalCcDropdownOpen: false,
            globalCcDropdownItems: [],
            globalCcSearching: false,

            // Estado de importación Excel
            importUploading: false,
            importTemplateDownloaded: false,
            importResults: null,   // null | { mapped, errors, rows, mappings }
            // Paso del flujo de importación: 'instructions' | 'upload' | 'results'
            importStep: 'instructions',

            // Options for create modal
            categories: [],
            productTypes: [],

            // Final confirmation
            submitting: false,
            suggestingDescriptions: false,

            // Partner creation modal
            partnerModal: {
                open: false,
                quotationId: null,
                name: '',
                nit: '',
                email: '',
                phone: '',
                address: '',
                cityId: null,
                cityName: '',
                cityInputText: '',
                cityDropdownOpen: false,
                cityDropdownItems: [],
                citySearching: false,
                categoryIds: [],
                catInputText: '',
                catDropdownOpen: false,
                catDropdownItems: [],
                submitting: false,
                error: null,
            },

            // Dirección de entrega de la SDC completa
            deliveryData: null,   // null | { name, email, phone, address }
            // Mini-wizard de dirección de entrega
            deliveryModal: {
                open: false,
                name: '',
                email: '',
                phone: '',
                address: '',
                error: null,
            },

            // Create product modal
            createModal: {
                open: false,
                lineId: null,
                // Modo: 'product' (nuevo producto+variante) | 'variant' (solo variante)
                mode: "product",
                productName: "",
                categoryId: "",
                typeProductId: "",
                description: "",
                variantName: "",
                estimatedPrice: "",
                // Búsqueda de producto existente (modo variante)
                selectedProductId: null,
                selectedProductName: "",
                productSearchText: "",
                productDropdownOpen: false,
                productDropdownItems: [],
                productSearching: false,
                submitting: false,
                suggestingDescription: false,
                error: null,
                // Advertencias de similitud (bloquean el guardado)
                productWarning: null,         // nombre de producto ya existe
                productWarningMatches: [],    // productos similares encontrados
                variantWarning: null,         // nombre de variante ya existe
                variantWarningMatches: [],    // variantes similares encontradas
                // Variantes pre-cargadas para check sincrónico (sin RPC por tecla)
                selectedProductVariants: [],  // variantes del producto seleccionado (modo 'variant')
                warningProductVariants: [],   // variantes del primer productWarningMatch (modo 'product')
            },

        });

        onWillStart(async () => {
            await this._fetchData();
        });

        const applyDialogSize = () => {
            const el = this.rootRef.el;
            if (!el) return;
            const modalDialog = el.closest('.modal-dialog');
            if (!modalDialog) return;
            if (this.state.wizardMode === 'manual') {
                modalDialog.classList.add('om-dialog-manual');
            } else {
                modalDialog.classList.remove('om-dialog-manual');
            }
        };
        onMounted(applyDialogSize);
        onPatched(applyDialogSize);
    }

    async _fetchData() {
        if (!this.props.quotationId) {
            this.state.loading = false;
            this.state.error = "No se encontró el ID de la solicitud.";
            return;
        }
        try {
            const result = await rpc("/purchase_management/get_order_mapping_data", {
                quotation_id: this.props.quotationId,
            });
            if (result.error) {
                this.state.error = result.error;
            } else {
                this.state.reference = result.reference || "";
                this.state.subject = result.subject || "";
                this.state.requestType = result.request_type || "";
                this.state.projectId = result.project_id || null;
                this.state.categories = result.categories || [];
                this.state.productTypes = result.product_types || [];
                // CC global por defecto
                this.state.globalCostCenterId = result.default_cost_center_id || null;
                this.state.globalCostCenterName = result.default_cost_center_name || '';
                this.state.lines = (result.lines || []).map((l) => {
                    const suggestions = l.suggestions || [];
                    let preselected = null;

                    // Variante ya guardada en BD
                    if (l.warehouse_variant_id) {
                        preselected = suggestions.find((s) => s.id === l.warehouse_variant_id) || null;
                        if (!preselected) {
                            preselected = { id: l.warehouse_variant_id, name: '', productName: '', category: '' };
                        }
                    }
                    // Sin asignación previa: usar pre-selección calculada en el servidor
                    else if (l.preselected_variant_id) {
                        preselected = {
                            id: l.preselected_variant_id,
                            name: l.preselected_variant_name || '',
                            productName: l.preselected_product_name || '',
                            category: l.preselected_category || '',
                        };
                    }

                    // Distribución multi-proveedor: una entrada por proveedor adjudicado
                    const distributions = (l.awarded_suppliers || []).map((s) => ({
                        quotation_id: s.quotation_id,
                        qline_id: s.qline_id,
                        partner_name: s.partner_name,
                        unit_price: s.unit_price || 0,
                        unit_price_cop: s.unit_price_cop,
                        currency_name: s.currency_name || 'COP',
                        currency_id: s.currency_id || null,
                        trm: s.trm || 1,
                        assigned_qty: s.assigned_qty || 0,
                        partnerFound: s.partner_found !== false,
                        partnerId: s.partner_id || null,
                        paymentTermId: null,
                        paymentTermName: s.payment_term_name || '',
                    }));

                    return {
                        id: l.id,
                        name: l.name,
                        qty: l.qty,
                        uom: l.uom,
                        specification: l.specification || "",
                        // Precio unitario en COP de la cotización adjudicada (0 si no hay)
                        awardedUnitPriceCop: l.awarded_unit_price_cop || 0,
                        suggestions,
                        selectedVariantId: preselected ? preselected.id : null,
                        selectedVariantName: preselected?.name || null,
                        selectedVariantProductName: preselected?.productName || null,
                        selectedVariantCategory: preselected?.category || null,
                        // Auto-match guardado (alias o preselección) — permite restablecer
                        autoVariantId: preselected ? preselected.id : null,
                        autoVariantName: preselected?.name || null,
                        autoVariantProductName: preselected?.productName || null,
                        autoVariantCategory: preselected?.category || null,
                        // Creación diferida: datos de una variante pendiente (no en BD aún)
                        pendingCreation: null,
                        // Distribución de cantidades por proveedor adjudicado
                        distributions,
                        // Índice del proveedor visible en el carousel (modo manual)
                        carouselIndex: 0,
                        // M2o dropdown state
                        inputText: "",
                        dropdownOpen: false,
                        dropdownItems: [],
                        searching: false,
                        // Cost center state — usa el CC global como default si la línea no tiene uno
                        costCenterId: l.cost_center_id || result.default_cost_center_id || null,
                        costCenterName: l.cost_center_name || result.default_cost_center_name || null,
                        ccInputText: "",
                        ccDropdownOpen: false,
                        ccDropdownItems: [],
                        ccSearching: false,
                    };
                });

                // Saltar al primer índice no mapeado — las líneas con alias ya están listas
                const firstUnmapped = this.state.lines.findIndex(
                    (l) => !((!!l.selectedVariantId || !!l.pendingCreation) && !!l.costCenterId)
                );
                if (firstUnmapped >= 0) this.state.wizardIndex = firstUnmapped;
            }
        } catch (e) {
            this.state.error = "Error al cargar los datos: " + (e.message || String(e));
        } finally {
            this.state.loading = false;
        }
    }


    selectVariant(lineId, variant) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.selectedVariantId = variant.id;
        line.selectedVariantName = variant.name;
        line.selectedVariantProductName = variant.productName || null;

        line.selectedVariantCategory = variant.category || null;
        line.pendingCreation = null;
        line.inputText = "";
        line.dropdownOpen = false;
        line.dropdownItems = [];
        clearTimeout(this._debounceTimers[lineId]);
        // Auto-avance si el CC ya está asignado y no hay distribución pendiente
        if (line.costCenterId && line.distributions.length <= 1 && this.hasNext) {
            setTimeout(() => this.goNext(), 500);
        }
    }

    clearVariant(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;

        // Si esta línea era el CREADOR de un producto pendiente (mode='product'),
        // limpiar en cascada todas las líneas que dependan de él (mode='variant_of_pending').
        if (line.pendingCreation && line.pendingCreation.mode === 'product') {
            const parentName = (line.pendingCreation.product_name || '').toLowerCase();
            let cascadeCount = 0;
            for (const l of this.state.lines) {
                if (l.id === lineId || !l.pendingCreation) continue;
                if (
                    l.pendingCreation.mode === 'variant_of_pending' &&
                    (l.pendingCreation.pending_product_name || '').toLowerCase() === parentName
                ) {
                    l.pendingCreation = null;
                    l.selectedVariantId = null;
                    l.selectedVariantName = null;
                    l.selectedVariantProductName = null;
                    l.selectedVariantCategory = null;
                    l.inputText = "";
                    l.dropdownOpen = false;
                    l.dropdownItems = [];
                    cascadeCount++;
                }
            }
            if (cascadeCount > 0) {
                this.notification.add(
                    `Se eliminaron ${cascadeCount} variante(s) asociada(s) a "${line.pendingCreation.product_name}" ` +
                    `porque el producto ya no será creado.`,
                    { type: 'warning' }
                );
            }
        }

        line.selectedVariantId = null;
        line.selectedVariantName = null;
        line.selectedVariantProductName = null;
        line.selectedVariantCategory = null;
        line.pendingCreation = null;
        line.inputText = "";
        line.dropdownOpen = false;
        line.dropdownItems = [];
        clearTimeout(this._debounceTimers[lineId]);
    }

    /**
     * Restablece la vinculación automática (alias o preselección del servidor).
     * Se usa cuando el usuario quitó el vínculo y quiere restaurarlo.
     */
    resetToAuto(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line || !line.autoVariantId) return;
        line.selectedVariantId = line.autoVariantId;
        line.selectedVariantName = line.autoVariantName;
        line.selectedVariantProductName = line.autoVariantProductName;
        line.selectedVariantCategory = line.autoVariantCategory;
        line.pendingCreation = null;
        line.inputText = "";
        line.dropdownOpen = false;
        line.dropdownItems = [];
        clearTimeout(this._debounceTimers[lineId]);
    }

    // Cost center selection

    selectCostCenter(lineId, cc) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.costCenterId = cc.id;
        line.costCenterName = cc.name;
        line.ccInputText = "";
        line.ccDropdownOpen = false;
        line.ccDropdownItems = [];
        clearTimeout(this._ccDebounceTimers[lineId]);
        // Auto-avance si la variante ya está asignada y no hay distribución pendiente
        if ((line.selectedVariantId || line.pendingCreation) && line.distributions.length <= 1 && this.hasNext) {
            setTimeout(() => this.goNext(), 500);
        }
    }

    clearCostCenter(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.costCenterId = null;
        line.costCenterName = null;
        line.ccInputText = "";
        line.ccDropdownOpen = false;
        line.ccDropdownItems = [];
        clearTimeout(this._ccDebounceTimers[lineId]);
    }

    onCcInputMousedown(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.ccDropdownOpen = true;
        if (!line.ccDropdownItems.length) {
            this._loadCostCenterItems(lineId, line.ccInputText.trim());
        }
    }

    onCcInputBlur(lineId) {
        setTimeout(() => {
            const line = this.state.lines.find((l) => l.id === lineId);
            if (line) line.ccDropdownOpen = false;
        }, 200);
    }

    onCcInputChange(lineId, ev) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.ccInputText = ev.target.value;
        line.ccDropdownOpen = true;
        clearTimeout(this._ccDebounceTimers[lineId]);
        this._ccDebounceTimers[lineId] = setTimeout(() => {
            this._loadCostCenterItems(lineId, line.ccInputText.trim());
        }, 300);
    }

    onCcInputKeydown(lineId, ev) {
        if (ev.key === "Escape") {
            const line = this.state.lines.find((l) => l.id === lineId);
            if (line) {
                line.ccDropdownOpen = false;
                clearTimeout(this._ccDebounceTimers[lineId]);
            }
        }
    }

    onCcItemMousedown(lineId, cc) {
        this.selectCostCenter(lineId, cc);
    }

    async _loadCostCenterItems(lineId, term) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.ccSearching = true;
        try {
            const result = await rpc("/purchase_management/search_cost_centers", {
                search_term: term,
                limit: 6,
                project_id: this.state.projectId,
                request_type: this.state.requestType,
            });
            line.ccDropdownItems = result.error ? [] : (result.cost_centers || []);
        } catch (_) {
            line.ccDropdownItems = [];
        } finally {
            line.ccSearching = false;
        }
    }

    getCostCenterLabel(line) {
        return line.costCenterName || "";
    }

    // M2o-style dropdown

    onInputMousedown(lineId) {
        // El Dialog de Odoo auto-enfoca el primer input al abrirse (dispara focus sin mousedown).
        // Movemos aquí la apertura del dropdown para que solo responda a clics reales del usuario,
        // incluso cuando el campo ya está enfocado y el navegador no vuelve a disparar focus.
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.dropdownOpen = true;
        if (!line.dropdownItems.length) {
            this._loadDropdownItems(lineId, line.inputText.trim());
        }
    }

    onInputBlur(lineId) {
        setTimeout(() => {
            const line = this.state.lines.find((l) => l.id === lineId);
            if (line) {
                line.dropdownOpen = false;
            }
        }, 200);
    }

    onInputChange(lineId, ev) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.inputText = ev.target.value;
        line.dropdownOpen = true;
        clearTimeout(this._debounceTimers[lineId]);
        this._debounceTimers[lineId] = setTimeout(() => {
            this._loadDropdownItems(lineId, line.inputText.trim());
        }, 300);
    }

    onInputKeydown(lineId, ev) {
        if (ev.key === "Escape") {
            const line = this.state.lines.find((l) => l.id === lineId);
            if (line) {
                line.dropdownOpen = false;
                clearTimeout(this._debounceTimers[lineId]);
            }
        }
    }

    onItemMousedown(lineId, variant) {
        this.selectVariant(lineId, variant);
    }

    async _loadDropdownItems(lineId, term) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.searching = true;
        try {
            const result = await rpc("/purchase_management/search_warehouse_products", {
                search_term: term,
                limit: 6,
            });
            if (!result.error) {
                const serverVariants = result.products || [];
                const suggestionIds = new Set(line.suggestions.map((s) => s.id));

                const suggItems = [];
                const otherItems = [];

                if (!term) {
                    line.suggestions.forEach((s) => {
                        suggItems.push({ ...s, isSuggestion: true });
                    });
                    serverVariants
                        .filter((v) => !suggestionIds.has(v.id))
                        .forEach((v) => otherItems.push({ ...v, isSuggestion: false }));
                } else {
                    serverVariants.forEach((v) => {
                        if (suggestionIds.has(v.id)) {
                            suggItems.push({ ...v, isSuggestion: true });
                        } else {
                            otherItems.push({ ...v, isSuggestion: false });
                        }
                    });
                }

                line.dropdownItems = [...suggItems, ...otherItems];
            } else {
                line.dropdownItems = [];
            }
        } catch (_) {
            line.dropdownItems = [];
        } finally {
            line.searching = false;
        }
    }

    // Create product modal — DEFERRED CREATION
    // Las variantes NO se crean en BD al guardar el modal.
    // Se almacenan en pendingCreation y se crean al confirmar.

    openCreateModal(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        const m = this.state.createModal;
        m.open = true;
        m.lineId = lineId;

        // Nombre del producto: primera palabra del nombre de la línea (categoría genérica)
        const fullName = (line ? (line.name || "") : "").trim();
        m.productName = fullName.split(/\s+/)[0] || fullName;

        // Nombre de la variante: el usuario lo completa manualmente
        m.variantName = "";

        m.categoryId = "";

        // Pre-seleccionar tipo "Producto" si la solicitud es de tipo Productos
        const isProductRequest = this.state.requestType.trim().toLowerCase() === 'productos';
        if (isProductRequest) {
            const match = this.state.productTypes.find(
                (t) => t.name.trim().toLowerCase() === 'producto'
            );
            m.typeProductId = match ? String(match.id) : "";
        } else {
            m.typeProductId = "";
        }

        // Precio estimado: precio unitario en COP de la cotización adjudicada
        m.estimatedPrice = (line && line.awardedUnitPriceCop) ? String(line.awardedUnitPriceCop) : "";

        m.description = "";
        m.submitting = false;
        m.error = null;
        m.productWarning = null;
        m.productWarningMatches = [];
        m.variantWarning = null;
        m.variantWarningMatches = [];
        m.selectedProductVariants = [];
        m.warningProductVariants = [];
        // Resetear modo y búsqueda de producto al abrir
        m.mode = "product";
        m.selectedProductId = null;
        m.selectedProductName = "";
        m.selectedPendingProductName = null;
        m.productSearchText = "";
        m.productDropdownOpen = false;
        m.productDropdownItems = [];
        m.productSearching = false;
        if (line) line.dropdownOpen = false;

        // Check inmediato para el nombre pre-llenado (un solo RPC, no timer)
        if (m.productName && m.productName.length >= 3) {
            this._checkProductName(m.productName);
        }
    }

    closeCreateModal() {
        this.state.createModal.open = false;
    }

    editPendingCreation(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line || !line.pendingCreation) return;
        const pc = line.pendingCreation;
        const m = this.state.createModal;

        m.open = true;
        m.lineId = lineId;
        m.error = null;
        m.submitting = false;
        m.productWarning = null;
        m.productWarningMatches = [];
        m.variantWarning = null;
        m.variantWarningMatches = [];
        m.selectedProductVariants = [];
        m.warningProductVariants = [];
        m.productDropdownOpen = false;
        m.productDropdownItems = [];
        m.productSearching = false;

        m.variantName = pc.variant_name || '';
        m.estimatedPrice = pc.estimated_price ? String(pc.estimated_price) : '';

        if (pc.mode === 'product') {
            m.mode = 'product';
            m.productName = pc.product_name || '';
            m.categoryId = pc.category_id ? String(pc.category_id) : '';
            m.typeProductId = pc.type_product_id ? String(pc.type_product_id) : '';
            m.description = pc.description || '';
            m.selectedProductId = null;
            m.selectedProductName = '';
            m.selectedPendingProductName = null;
            m.productSearchText = '';
        } else if (pc.mode === 'variant') {
            m.mode = 'variant';
            m.productName = '';
            m.categoryId = '';
            m.typeProductId = '';
            m.description = '';
            m.selectedProductId = pc.product_id || null;
            m.selectedProductName = pc.product_name || '';
            m.selectedPendingProductName = null;
            m.productSearchText = pc.product_name || '';
        } else if (pc.mode === 'variant_of_pending') {
            m.mode = 'variant';
            m.productName = '';
            m.categoryId = '';
            m.typeProductId = '';
            m.description = '';
            m.selectedProductId = `pending:${pc.pending_product_name}`;
            m.selectedProductName = pc.pending_product_name || '';
            m.selectedPendingProductName = pc.pending_product_name || '';
            m.productSearchText = pc.pending_product_name || '';
        }

        if (m.mode === 'product' && m.productName && m.productName.trim().length >= 3) {
            this._checkProductName(m.productName.trim());
        }
    }

    // Alterna entre modo 'product' y 'variant' — los datos de cada modo se conservan
    // para que el usuario pueda cambiar y volver sin perder lo que había llenado.
    // El reset completo ocurre solo en openCreateModal al abrir el modal.
    setCreateMode(mode) {
        const m = this.state.createModal;
        if (m.mode === mode) return;
        m.mode = mode;
        m.error = null;
        m.productWarning = null;
        m.productWarningMatches = [];
        m.variantWarning = null;
        m.variantWarningMatches = [];
        m.warningProductVariants = [];
        m.selectedProductVariants = [];
        // Re-ejecutar checks con los datos ya escritos al cambiar de modo
        if (mode === 'product' && m.productName && m.productName.trim().length >= 3) {
            this._checkProductName(m.productName.trim());
        } else if (mode === 'variant' && m.variantName && m.variantName.trim().length >= 3) {
            this._checkVariantName(m.variantName.trim());
        }
    }

    // Búsqueda de producto existente (modo variante) 

    onProductSearchMousedown() {
        const m = this.state.createModal;
        m.productDropdownOpen = true;
        if (!m.productDropdownItems.length) this._loadProductTemplateItems(m.productSearchText.trim());
    }

    onProductSearchBlur() {
        setTimeout(() => { this.state.createModal.productDropdownOpen = false; }, 200);
    }

    onProductSearchChange(ev) {
        const m = this.state.createModal;
        m.productSearchText = ev.target.value;
        m.productDropdownOpen = true;
        clearTimeout(this._productSearchTimer);
        this._productSearchTimer = setTimeout(() => {
            this._loadProductTemplateItems(m.productSearchText.trim());
        }, 300);
    }

    onProductSearchKeydown(ev) {
        if (ev.key === "Escape") {
            this.state.createModal.productDropdownOpen = false;
            clearTimeout(this._productSearchTimer);
        }
    }

    async onProductTemplateMousedown(product) {
        const m = this.state.createModal;
        m.selectedProductId = product.id;
        m.selectedProductName = product.name;
        m.productSearchText = "";
        m.productDropdownOpen = false;
        m.productDropdownItems = [];
        m.error = null;
        m.selectedProductVariants = [];
        m.variantWarning = null;
        m.variantWarningMatches = [];

        if (product.__pending__) {
            // Producto pendiente de otra línea — sin RPC, ya tendrá variantes solo cuando se confirme
            m.selectedPendingProductName = product.name;
        } else {
            m.selectedPendingProductName = null;
            // Pre-cargar variantes del producto elegido para el check sincrónico de variante
            try {
                const result = await rpc('/purchase_management/search_warehouse_products', {
                    product_id: product.id,
                    limit: 50,
                });
                m.selectedProductVariants = result.products || [];
            } catch (_) { /* silencioso */ }
        }
    }

    clearSelectedProduct() {
        const m = this.state.createModal;
        m.selectedProductId = null;
        m.selectedProductName = "";
        m.selectedPendingProductName = null;
        m.productSearchText = "";
        m.productDropdownOpen = false;
        m.productDropdownItems = [];
        m.variantWarning = null;
        m.variantWarningMatches = [];
        m.selectedProductVariants = [];
    }

    async _loadProductTemplateItems(term) {
        const m = this.state.createModal;
        m.productSearching = true;
        try {
            const result = await rpc("/purchase_management/search_warehouse_product_templates", {
                search_term: term,
                limit: 8,
            });
            const realItems = result.error ? [] : (result.products || []);
            // Inyectar productos pendientes de otras líneas que coincidan con el término
            const lowerTerm = (term || '').toLowerCase();
            const pendingItems = this.pendingProductsOnOtherLines.filter((p) =>
                !lowerTerm || p.name.toLowerCase().includes(lowerTerm)
            );
            m.productDropdownItems = [...pendingItems, ...realItems];
        } catch (_) {
            m.productDropdownItems = [];
        } finally {
            m.productSearching = false;
        }
    }

    // Retorna los productos pendientes de creación registrados en otras líneas del wizard.
    // Usado para mostrarlos en el dropdown de búsqueda en modo variante.
    get pendingProductsOnOtherLines() {
        const currentLineId = this.state.createModal.lineId;
        const seen = new Set();
        const result = [];
        for (const l of this.state.lines) {
            if (l.id === currentLineId) continue;
            if (!l.pendingCreation || l.pendingCreation.mode !== 'product') continue;
            const name = l.pendingCreation.product_name;
            if (!name || seen.has(name)) continue;
            seen.add(name);
            result.push({ id: `__pending__:${name}`, name, __pending__: true });
        }
        return result;
    }

    // Posiciona el dropdown del buscador de producto (mismo truco portal que el wizard)
    getProductDropdownStyle() {
        return this._fixedDropdownStyle(document.querySelector('[data-dd-pt="modal"]'));
    }

    // Getter para mostrar el precio con puntos de miles (ej. 1.500.000)
    get formattedEstimatedPrice() {
        const raw = String(this.state.createModal.estimatedPrice || '').replace(/\D/g, '');
        if (!raw) return '';
        return raw.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    // Línea de solicitud asociada al modal de creación (para mostrar contexto al usuario)
    get createModalLine() {
        if (!this.state.createModal.lineId) return null;
        return this.state.lines.find((l) => l.id === this.state.createModal.lineId) || null;
    }

    onModalFieldChange(field, ev) {
        if (field === 'estimatedPrice') {
            // Extraer solo dígitos y guardar el valor raw en el estado
            const raw = ev.target.value.replace(/\D/g, '');
            this.state.createModal.estimatedPrice = raw;
            // Reformatear el input con puntos de miles sin esperar el re-render
            ev.target.value = raw ? raw.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '';
        } else {
            this.state.createModal[field] = ev.target.value;
        }
        // Duplicate checks fire on blur, not per keystroke
    }

    /**
     * Check de nombre de producto contra el catálogo.
     * Se llama al salir del campo (blur) y al abrir el modal con nombre pre-llenado.
     * Un solo RPC; también pre-carga las variantes del primer match para el check sincrónico.
     */
    async _checkProductName(name) {
        const m = this.state.createModal;
        m.productWarning = null;
        m.productWarningMatches = [];
        m.variantWarning = null;
        m.variantWarningMatches = [];
        m.warningProductVariants = [];
        if (!name || name.length < 3) return;

        // ── Verificar primero contra productos pendientes de otras líneas (sin RPC) ──
        const lowerName = name.toLowerCase();
        const matchingPending = this.pendingProductsOnOtherLines.find((p) => {
            const lowerPending = p.name.toLowerCase();
            return lowerPending === lowerName ||
                   lowerPending.startsWith(lowerName) ||
                   lowerName.startsWith(lowerPending);
        });
        if (matchingPending) {
            m.productWarning = `"${matchingPending.name}" ya está siendo creado en otra línea de este wizard. ` +
                               `Cambia a modo Variante y selecciónalo para agregar solo la variante nueva.`;
            return; // Sin RPC al catálogo
        }

        try {
            const result = await rpc('/purchase_management/search_warehouse_product_templates', {
                search_term: name,
                limit: 3,
            });
            const matches = result.products || [];
            if (matches.length > 0) {
                m.productWarning = 'Ya existe un producto con nombre similar en el catálogo.';
                m.productWarningMatches = matches;
                // Pre-cargar variantes del primer match para el check sincrónico de variante
                try {
                    const vResult = await rpc('/purchase_management/search_warehouse_products', {
                        product_id: matches[0].id,
                        limit: 50,
                    });
                    m.warningProductVariants = vResult.products || [];
                } catch (_) { /* silencioso */ }
                // Si el usuario ya escribió variante, chequear sincrónicamente
                if (m.variantName && m.variantName.trim().length >= 3) {
                    this._checkVariantName(m.variantName.trim());
                }
            }
        } catch (_) { /* silencioso */ }
    }

    /**
     * Check sincrónico de nombre de variante contra las variantes pre-cargadas.
     * Sin RPC, sin timer — se ejecuta al salir del campo (blur).
     * Modo 'variant': compara contra selectedProductVariants (cargadas al elegir producto).
     * Modo 'product': compara contra warningProductVariants (cargadas al hacer blur en productName).
     */
    // Retorna las variantes ya comprometidas (en otras líneas) para el producto pendiente
    // que está seleccionado en el modal. Usado por _checkVariantName para evitar duplicados.
    get pendingVariantsForSelectedProduct() {
        const m = this.state.createModal;
        const targetName = (m.selectedPendingProductName || '').toLowerCase();
        if (!targetName) return [];
        const currentLineId = m.lineId;
        const result = [];
        for (const l of this.state.lines) {
            if (l.id === currentLineId || !l.pendingCreation) continue;
            const pc = l.pendingCreation;
            const pcName = (pc.product_name || pc.pending_product_name || '').toLowerCase();
            if (pcName !== targetName) continue;
            if (pc.mode === 'product' || pc.mode === 'variant_of_pending') {
                if (pc.variant_name) result.push({ name: pc.variant_name });
            }
        }
        return result;
    }

    _checkVariantName(variantName) {
        const m = this.state.createModal;
        m.variantWarning = null;
        m.variantWarningMatches = [];
        if (!variantName || variantName.length < 3) return;

        // Modo variante sobre producto pendiente: comparar contra variantes ya registradas
        // en otras líneas del mismo producto pendiente (sin RPC).
        if (m.mode === 'variant' && m.selectedPendingProductName) {
            const pool = this.pendingVariantsForSelectedProduct;
            if (pool.length > 0) {
                const needle = variantName.toLowerCase();
                const matched = pool.filter((v) => {
                    const h = (v.name || '').toLowerCase();
                    return h === needle || h.includes(needle) || needle.includes(h);
                });
                if (matched.length > 0) {
                    m.variantWarning = `La variante "${matched[0].name}" ya fue asignada a este producto en otra línea.`;
                    m.variantWarningMatches = matched;
                }
            }
            return; // No continuar con el pool del catálogo real
        }

        const pool = m.mode === 'variant' ? m.selectedProductVariants : m.warningProductVariants;
        if (!pool || pool.length === 0) return;

        const needle = variantName.toLowerCase();
        const needleWords = new Set(needle.split(/\s+/).filter((w) => w.length > 1));
        const matched = [];

        for (const v of pool) {
            const haystack = (v.name || '').toLowerCase();
            if (haystack.includes(needle) || needle.includes(haystack)) {
                matched.push(v);
                continue;
            }
            const haystackWords = new Set(haystack.split(/\s+/).filter((w) => w.length > 1));
            if (needleWords.size > 0 && haystackWords.size > 0) {
                let common = 0;
                for (const w of needleWords) { if (haystackWords.has(w)) common++; }
                if (common / Math.max(needleWords.size, haystackWords.size) >= 0.5) {
                    matched.push(v);
                }
            }
        }

        if (matched.length > 0) {
            m.variantWarning = 'Ya existe una variante con nombre similar en este producto.';
            m.variantWarningMatches = matched;
        }
    }

    // ── Sentence case — primera letra mayúscula, el resto minúscula ────────────
    _toSentenceCase(str) {
        if (!str) return str;
        const t = str.trim();
        return t.charAt(0).toUpperCase() + t.slice(1).toLowerCase();
    }

    // ── Contadores de caracteres (sin espacios / sin caracteres especiales) ──
    get productNameCharCount() {
        return (this.state.createModal.productName || '').replace(/\s/g, '').length;
    }

    get descriptionCharCount() {
        return (this.state.createModal.description || '')
            .replace(/[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜ0-9]/g, '').length;
    }

    // Handlers de blur para los inputs del modal de creación
    onProductNameBlur(ev) {
        const raw = (ev.target.value || '').trim();
        const cased = this._toSentenceCase(raw);
        this.state.createModal.productName = cased;
        ev.target.value = cased;
        if (this.state.createModal.mode === 'product') {
            this._checkProductName(cased);
        }
    }

    onVariantNameBlur(ev) {
        const raw = (ev.target.value || '').trim();
        const cased = this._toSentenceCase(raw);
        this.state.createModal.variantName = cased;
        ev.target.value = cased;
        this._checkVariantName(cased);
    }

    onDescriptionBlur(ev) {
        const raw = (ev.target.value || '').trim();
        const cased = this._toSentenceCase(raw);
        this.state.createModal.description = cased;
        ev.target.value = cased;
    }

    /**
     * Consulta DuckDuckGo via proxy backend y rellena el campo Descripción
     * del modal de creación manual.
     */
    async onSuggestDescription() {
        const m = this.state.createModal;
        const productName = (m.productName || '').trim();
        if (!productName) {
            this.notification.add('Escribe primero el nombre del producto.', { type: 'warning' });
            return;
        }
        m.suggestingDescription = true;
        try {
            const result = await rpc('/purchase_management/suggest_description', { product_name: productName });
            if (result.error || !result.description) {
                this.notification.add(result.error || 'No se encontró información para este producto.', { type: 'warning' });
                return;
            }
            m.description = this._toSentenceCase(result.description);
        } catch (e) {
            this.notification.add('Error al contactar el servicio de sugerencias.', { type: 'warning' });
        } finally {
            m.suggestingDescription = false;
        }
    }

    /**
     * Modo Excel: itera sobre filas con pending_creation modo 'product' sin descripción
     * y solicita sugerencia para cada una.
     */
    async onSuggestAllDescriptions() {
        if (this.state.suggestingDescriptions) return;
        this.state.suggestingDescriptions = true;

        const targets = ((this.state.importResults?.rows) || []).filter(
            (r) => r.status === 'ok' &&
                   r.pending_creation?.mode === 'product' &&
                   !(r.pending_creation.description || '').trim()
        );

        if (!targets.length) {
            this.notification.add('No hay productos nuevos con descripción vacía.', { type: 'info' });
            this.state.suggestingDescriptions = false;
            return;
        }

        let filled = 0, failed = 0;
        for (const row of targets) {
            try {
                const result = await rpc('/purchase_management/suggest_description', {
                    product_name: (row.pending_creation.product_name || '').trim(),
                });
                if (result.error || !result.description) { failed++; continue; }
                const desc = this._toSentenceCase(result.description);
                // Actualizar importResults.rows (reactivo, lo ve el XML)
                row.pending_creation.description = desc;
                // Sincronizar en state.lines (lo envía onConfirm al backend)
                const line = this.state.lines.find((l) => l.id === row.line_id);
                if (line?.pendingCreation) line.pendingCreation.description = desc;
                filled++;
            } catch (_e) { failed++; }
        }

        this.state.suggestingDescriptions = false;
        if (filled > 0 && failed === 0)
            this.notification.add(`${filled} descripción(es) sugerida(s) correctamente.`, { type: 'success' });
        else if (filled > 0)
            this.notification.add(`${filled} sugerida(s). ${failed} no pudieron obtenerse.`, { type: 'warning' });
        else
            this.notification.add('No se pudo obtener ninguna descripción de los servicios externos.', { type: 'danger' });
    }

    /**
     * Guarda los datos del modal como pendingCreation en la línea (creación diferida).
     * La variante NO se crea en BD aquí — se creará al hacer clic en Confirmar.
     */
    onSaveNewProduct() {
        const m = this.state.createModal;
        m.error = null;

        const hasProductBlock = m.mode === 'product' && !!m.productWarning;
        const hasVariantBlock = !!m.variantWarning;
        if (hasProductBlock || hasVariantBlock) {
            m.error = 'Corrige las coincidencias detectadas antes de guardar. Si el producto es diferente, cambia el nombre para que no coincida con los existentes.';
            return;
        }

        // ── Modo Variante: agrega variante a producto existente o pendiente ──
        if (m.mode === 'variant') {
            if (!m.selectedProductId) {
                m.error = "Debes seleccionar un producto existente.";
                return;
            }
            if (!m.variantName.trim()) {
                m.error = "El nombre de la variante es obligatorio.";
                return;
            }
            const price = parseFloat(m.estimatedPrice);
            if (!m.estimatedPrice || isNaN(price) || price <= 0) {
                m.error = "El precio estimado debe ser un número mayor a 0.";
                return;
            }

            // ¿El producto seleccionado es un pendiente de otra línea?
            if (m.selectedPendingProductName) {
                // Guardia final: verificar que no exista ya la misma variante en el mismo pendiente
                const newVariantLower = m.variantName.trim().toLowerCase();
                const alreadyTaken = this.pendingVariantsForSelectedProduct.find(
                    (v) => (v.name || '').toLowerCase() === newVariantLower
                );
                if (alreadyTaken) {
                    m.error = `La variante "${alreadyTaken.name}" ya está asignada a este producto en otra línea.`;
                    return;
                }
                const pendingCreation = {
                    mode: 'variant_of_pending',
                    pending_product_name: m.selectedPendingProductName,
                    variant_name: m.variantName.trim(),
                    estimated_price: price,
                };
                this._applyPendingCreation(m.lineId, pendingCreation, m.selectedPendingProductName, m.variantName.trim());
                this.closeCreateModal();
                return;
            }

            // Producto real ya en BD
            const pendingCreation = {
                mode: 'variant',
                product_id: m.selectedProductId,
                product_name: m.selectedProductName,
                variant_name: m.variantName.trim(),
                estimated_price: price,
            };
            this._applyPendingCreation(m.lineId, pendingCreation, m.selectedProductName, m.variantName.trim());
            this.closeCreateModal();
            return;
        }

        // ── Modo Producto: crea producto + primera variante ───────────────────
        if (
            !m.productName.trim() ||
            !m.categoryId ||
            !m.typeProductId ||
            !m.description.trim() ||
            !m.variantName.trim() ||
            !m.estimatedPrice
        ) {
            m.error = "Todos los campos son obligatorios.";
            return;
        }
        // ── Validación de límites de caracteres ────────────────────────────────
        const nameNoSpaces = (m.productName || '').replace(/\s/g, '');
        if (nameNoSpaces.length > 25) {
            m.error = 'El nombre del producto supera los 25 caracteres (sin contar espacios).';
            return;
        }
        const descCount = (m.description || '').replace(/[^a-zA-ZáéíóúÁÉÍÓÚñÑüÜ0-9]/g, '').length;
        if (descCount > 200) {
            m.error = 'La descripción supera los 200 caracteres (sin contar espacios ni caracteres especiales).';
            return;
        }

        const price = parseFloat(m.estimatedPrice);
        if (isNaN(price) || price <= 0) {
            m.error = "El precio estimado debe ser un número mayor a 0.";
            return;
        }

        const pendingCreation = {
            mode: 'product',
            product_name: m.productName.trim(),
            category_id: parseInt(m.categoryId, 10),
            type_product_id: parseInt(m.typeProductId, 10),
            description: m.description.trim(),
            variant_name: m.variantName.trim(),
            estimated_price: price,
        };
        this._applyPendingCreation(m.lineId, pendingCreation, m.productName.trim(), m.variantName.trim());
        this.closeCreateModal();
    }

    /**
     * Aplica una creación pendiente a una línea del wizard.
     * El variant_id se establece como '__pending__' para diferenciarlo de IDs reales.
     */
    _applyPendingCreation(lineId, pendingCreation, productName, variantName) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.pendingCreation = pendingCreation;
        line.selectedVariantId = '__pending__';
        line.selectedVariantName = variantName;
        line.selectedVariantProductName = productName;
        line.selectedVariantCategory = null;
        line.inputText = "";
        line.dropdownOpen = false;
        line.dropdownItems = [];
        clearTimeout(this._debounceTimers[lineId]);
        // Auto-avance si el CC ya está asignado y no hay distribución pendiente
        if (line.costCenterId && line.distributions.length <= 1 && this.hasNext) {
            setTimeout(() => this.goNext(), 500);
        }
        this.notification.add(
            `"${variantName}" pendiente de crear — se guardará al confirmar.`,
            { type: "info" }
        );
    }

    // ─────────────────────────────────────────────────────────────
    // Wizard — navegación
    // ─────────────────────────────────────────────────────────────

    get currentLine() {
        return this.state.lines[this.state.wizardIndex] || null;
    }

    get wizardProgress() {
        if (!this.state.lines.length) return 0;
        return (this.mappedCount / this.state.lines.length) * 100;
    }

    get hasPrev() { return this.state.wizardIndex > 0; }
    get hasNext() { return this.state.wizardIndex < this.state.lines.length - 1; }

    goNext() { if (this.hasNext) { this.state.wizardIndex++; this.closePartnerPanel(); } }
    goPrev() { if (this.hasPrev) { this.state.wizardIndex--; this.closePartnerPanel(); } }
    resetImport() {
        this.state.importResults = null;
        this.state.importUploading = false;
        this.state.importStep = 'main';
    }

    goToImportStep(step) {
        this.state.importStep = step;
    }
    goTo(idx) {
        if (idx >= 0 && idx < this.state.lines.length) {
            this.state.wizardIndex = idx;
            this.closePartnerPanel();
        }
    }

    // ─────────────────────────────────────────────────────────────
    // Carousel de proveedores (panel derecho modo manual)
    // ─────────────────────────────────────────────────────────────

    prevCarousel(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        if (line.carouselIndex > 0) { line.carouselIndex--; this.closePartnerPanel(); }
    }

    nextCarousel(lineId) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        const max = line.distributions.length - 1;
        if (line.carouselIndex < max) { line.carouselIndex++; this.closePartnerPanel(); }
    }

    goToCarousel(lineId, index) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        line.carouselIndex = index;
        this.closePartnerPanel();
    }

    isDistributionComplete(line) {
        if (line.distributions.length <= 1) return true;
        return this.getDistributionStatus(line) === 'ok';
    }

    getWizardDotClass(line, idx) {
        if (idx === this.state.wizardIndex) return "dot-active";
        if (this.isMapped(line)) {
            return this.isDistributionComplete(line) ? "dot-complete" : "dot-warning";
        }
        return "";
    }

    // ─────────────────────────────────────────────────────────────
    // Template helpers
    // ─────────────────────────────────────────────────────────────

    isMapped(line) {
        return (!!line.selectedVariantId || !!line.pendingCreation) && !!line.costCenterId;
    }

    isPendingVariant(line) {
        return line.selectedVariantId === '__pending__';
    }

    // Placeholder dinámico para variante — usa el nombre del producto como ejemplo
    getVariantPlaceholder(line) {
        const name = (line.name || '').trim();
        if (!name) return 'Buscar en bodega...';
        const truncated = name.length > 38 ? name.substring(0, 38) + '…' : name;
        return `Ej. ${truncated}`;
    }

    // ── Dropdown de posición fija (escapa el scroll del modal) ─────────────
    // Dialog de Odoo hace un portal hacia document.body, así que el contenido
    // del modal no es descendiente de this.el. Usamos document.querySelector
    // para encontrar el ancla independientemente de dónde esté en el DOM.
    _fixedDropdownStyle(anchor) {
        if (!anchor) return 'display:none';
        const r = anchor.getBoundingClientRect();
        return `position:fixed;top:${r.bottom + 2}px;left:${r.left}px;width:${r.width}px;z-index:10000;max-height:260px;overflow-y:auto;`;
    }

    getDropdownStyle(lineId) {
        return this._fixedDropdownStyle(
            document.querySelector(`[data-dd-v="${lineId}"]`)
        );
    }

    getCcDropdownStyle(lineId) {
        return this._fixedDropdownStyle(
            document.querySelector(`[data-dd-cc="${lineId}"]`)
        );
    }

    getVariantLabel(line) {
        if (this.isPendingVariant(line)) {
            const prod = line.selectedVariantProductName ? `${line.selectedVariantProductName} ` : '';
            return `${prod}${line.selectedVariantName || ''}`;
        }
        let label = "";
        if (line.selectedVariantProductName) label += line.selectedVariantProductName;
        if (line.selectedVariantName) label += ` ${line.selectedVariantName}`;
        return label;
    }

    getDropdownItemLabel(item) {
        let label = "";
        if (item.productName) label += item.productName;
        if (item.name) label += ` ${item.name}`;
        return label;
    }

    get mappedCount() {
        return this.state.lines.filter((l) => this.isMapped(l)).length;
    }

    get allMapped() {
        return (
            this.state.lines.length > 0 &&
            this.state.lines.every((l) => this.isMapped(l))
        );
    }

    /** Todo proveedor tiene partner en BD o fue creado en el wizard */
    get allPartnersResolved() {
        for (const line of this.state.lines) {
            for (const dist of (line.distributions || [])) {
                if (!dist.partnerFound && !dist.pendingPartnerData) return false;
            }
        }
        return true;
    }

    /** ¿Hay alguna línea con variante pendiente de crear? */
    get hasAnyPendingCreation() {
        return this.state.lines.some((l) => !!l.pendingCreation);
    }

    // Distribución de cantidades por proveedor adjudicado

    getDistributionTotal(line) {
        return line.distributions.reduce((acc, d) => acc + (Number(d.assigned_qty) || 0), 0);
    }

    /**
     * Retorna 'ok' | 'partial' | 'over' según la distribución total vs qty solicitada.
     * Con 0 o 1 proveedor no aplica distribución manual → siempre 'ok'.
     */
    getDistributionStatus(line) {
        if (line.distributions.length <= 1) return 'ok';
        const total = this.getDistributionTotal(line);
        if (total > line.qty) return 'over';
        if (total < line.qty) return 'partial';
        return 'ok';
    }

    onDistributionQtyChange(lineId, qlineId, ev) {
        const line = this.state.lines.find((l) => l.id === lineId);
        if (!line) return;
        const dist = line.distributions.find((d) => d.qline_id === qlineId);
        if (!dist) return;
        const raw = ev.target.value.replace(/[^0-9]/g, '');
        const val = raw ? parseInt(raw, 10) : 0;
        dist.assigned_qty = val >= 0 ? val : 0;
        // Clamp en el input
        ev.target.value = dist.assigned_qty;
    }

    formatPrice(amount) {
        if (!amount) return '0';
        return Math.round(amount).toLocaleString('es-CO');
    }

    // Modo wizard: manual / excel

    setWizardMode(mode) {
        if (this.state.wizardMode === mode) return;
        this.state.wizardMode = mode;
        if (mode === 'manual') {
            this.state.importResults = null;
        }
        if (mode === 'excel') {
            this.state.importStep = 'instructions';
            this.state.importResults = null;
            this.state.importTemplateDownloaded = false;
        }
    }

    // Centro de costo global

    onGlobalCcMousedown() {
        this.state.globalCcDropdownOpen = true;
        if (!this.state.globalCcDropdownItems.length) {
            this._loadGlobalCcItems(this.state.globalCcInputText.trim());
        }
    }

    onGlobalCcBlur() {
        setTimeout(() => { this.state.globalCcDropdownOpen = false; }, 200);
    }

    onGlobalCcChange(ev) {
        this.state.globalCcInputText = ev.target.value;
        this.state.globalCcDropdownOpen = true;
        clearTimeout(this._globalCcTimer);
        this._globalCcTimer = setTimeout(() => {
            this._loadGlobalCcItems(this.state.globalCcInputText.trim());
        }, 300);
    }

    onGlobalCcKeydown(ev) {
        if (ev.key === 'Escape') {
            this.state.globalCcDropdownOpen = false;
            clearTimeout(this._globalCcTimer);
        }
    }

    onGlobalCcItemMousedown(cc) {
        this.state.globalCostCenterId = cc.id;
        this.state.globalCostCenterName = cc.name;
        this.state.globalCcInputText = '';
        this.state.globalCcDropdownOpen = false;
        this.state.globalCcDropdownItems = [];
        // Propagar a todas las líneas sin CC asignado manualmente
        for (const line of this.state.lines) {
            if (!line.costCenterId) {
                line.costCenterId = cc.id;
                line.costCenterName = cc.name;
            }
        }
    }

    clearGlobalCc() {
        this.state.globalCostCenterId = null;
        this.state.globalCostCenterName = '';
        this.state.globalCcInputText = '';
        this.state.globalCcDropdownOpen = false;
        this.state.globalCcDropdownItems = [];
    }

    async _loadGlobalCcItems(term) {
        this.state.globalCcSearching = true;
        try {
            const result = await rpc("/purchase_management/search_cost_centers", {
                search_term: term,
                limit: 8,
                project_id: this.state.projectId,
                request_type: this.state.requestType,
            });
            this.state.globalCcDropdownItems = result.error ? [] : (result.cost_centers || []);
        } catch (_) {
            this.state.globalCcDropdownItems = [];
        } finally {
            this.state.globalCcSearching = false;
        }
    }

    getGlobalCcDropdownStyle() {
        const anchor = document.querySelector('[data-dd-gcc]');
        if (!anchor) return 'display:none';
        const r = anchor.getBoundingClientRect();
        const w = 300;
        // alinear a la derecha del chip para no salirse del modal
        const left = Math.max(8, r.right - w);
        return `position:fixed;top:${r.bottom + 4}px;left:${left}px;width:${w}px;z-index:10000;max-height:260px;overflow-y:auto;`;
    }

    // Importación por Excel

    async onDownloadTemplate() {
        const url = `/purchase_management/download_mapping_template?quotation_id=${this.props.quotationId}`;
        try {
            const resp = await fetch(url, { credentials: 'include' });
            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                this.notification.add(data.error || 'Error al generar la plantilla', { type: 'danger' });
                return;
            }
            const blob = await resp.blob();
            const disposition = resp.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="?([^"]+)"?/);
            const filename = match ? match[1] : `Productos - ${this.props.quotationId}.xlsx`;
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(a.href);
            this.state.importTemplateDownloaded = true;
        } catch (e) {
            this.notification.add('Error al descargar la plantilla: ' + e.message, { type: 'danger' });
        }
    }

    async onImportExcel(ev) {
        const file = ev.target.files[0];
        if (!file) return;

        // Validar extensión antes de enviar
        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            this.notification.add('Solo se aceptan archivos .xlsx', { type: 'warning' });
            ev.target.value = '';
            return;
        }

        // Si ya hay resultados cargados, pedir confirmación antes de reemplazar
        if (this.state.importResults) {
            const ok = window.confirm(
                'Ya tienes resultados cargados. ¿Deseas reemplazarlos con el nuevo archivo?'
            );
            if (!ok) {
                ev.target.value = '';
                return;
            }
        }

        this.state.importUploading = true;
        try {
            const fd = new FormData();
            fd.append('quotation_id', String(this.props.quotationId));
            fd.append('excel_file', file);
            const resp = await fetch('/purchase_management/import_mapping_excel', {
                method: 'POST',
                body: fd,
                credentials: 'include',
            });
            const result = await resp.json();
            if (result.error) {
                this.notification.add(result.error, { type: 'danger' });
                return;
            }
            this._applyImportResults(result);
            if (result.mapped > 0 && result.errors.length === 0) {
                const reutilizadas = (result.rows || []).filter((r) => r.status === 'ok' && r.already_existed).length;
                const creadas = result.mapped - reutilizadas;
                let msg = `${result.mapped} producto(s) listos para vincular.`;
                if (creadas > 0) msg += ` ${creadas} variante(s) nueva(s) creadas.`;
                if (reutilizadas > 0) msg += ` ${reutilizadas} reutilizada(s) del catálogo.`;
                this.notification.add(msg, { type: 'success' });
            }
        } catch (e) {
            this.notification.add('Error al importar: ' + e.message, { type: 'danger' });
        } finally {
            this.state.importUploading = false;
            // Limpiar el input para permitir re-subida del mismo archivo
            ev.target.value = '';
        }
    }

    _applyImportResults(result) {
        this.state.importResults = result;
        this.state.importStep = 'main';
        // Actualizar estado de las líneas con lo que vino del backend
        for (const row of (result.rows || [])) {
            if (row.status !== 'ok') continue;
            const line = this.state.lines.find((l) => l.id === row.line_id);
            if (!line) continue;
            if (row.pending_creation) {
                // Variante nueva: creación diferida al confirmar (igual que modo manual)
                line.selectedVariantId = '__pending__';
                line.pendingCreation = row.pending_creation;
            } else {
                // Variante ya existe en BD → vincular directo
                line.selectedVariantId = row.variant_id;
                line.pendingCreation = null;
            }
            line.selectedVariantName = row.variant_name || '';
            line.selectedVariantProductName = row.product_name || '';
            line.selectedVariantCategory = '';
            line.costCenterId = row.cost_center_id || this.state.globalCostCenterId;
            line.costCenterName = row.cost_center_name || this.state.globalCostCenterName || '';
        }
    }

    get importErrorCount() {
        return ((this.state.importResults?.rows) || []).filter((r) => r.status === 'error').length;
    }

    get importOkCount() {
        return ((this.state.importResults?.rows) || []).filter((r) => r.status === 'ok').length;
    }

    get importReutilizadaCount() {
        return ((this.state.importResults?.rows) || []).filter((r) => r.status === 'ok' && r.already_existed).length;
    }

    get importPendingCount() {
        return ((this.state.importResults?.rows) || []).filter((r) => r.status === 'ok' && r.pending_creation).length;
    }

    /** Filas pendientes de creación (modo 'product') con descripción vacía — controla el botón Sugerir en Excel */
    get importEmptyPendingProductCount() {
        return ((this.state.importResults?.rows) || []).filter(
            (r) => r.status === 'ok' &&
                   r.pending_creation?.mode === 'product' &&
                   !(r.pending_creation.description || '').trim()
        ).length;
    }

    /** Líneas con múltiples proveedores adjudicados (para mostrar panel distribución en Excel) */
    get excelMultiSupplierLines() {
        return this.state.lines.filter((l) => l.distributions.length > 1);
    }

    /** Abre Google con el nombre del producto + variante en una pestaña nueva */
    openProductSearch(productName, variantName) {
        const parts = [productName, variantName].filter(Boolean);
        const q = encodeURIComponent(parts.join(' '));
        window.open(`https://www.google.com/search?q=qué+es+${q}`, '_blank');
    }

    // ─────────────────────────────────────────────────────────────
    // Partner creation modal
    // ─────────────────────────────────────────────────────────────

    openPartnerPanel(dist) {
        const p = this.state.partnerModal;
        p.open = true;
        p.quotationId = dist.quotation_id;
        p.name = dist.partner_name || '';
        p.nit = '';
        p.email = '';
        p.phone = '';
        p.address = '';
        p.cityId = null;
        p.cityName = '';
        p.cityInputText = '';
        p.cityDropdownOpen = false;
        p.cityDropdownItems = [];
        p.citySearching = false;
        p.categoryIds = [];
        p.catInputText = '';
        p.catDropdownOpen = false;
        p.catDropdownItems = [];
        p.submitting = false;
        p.error = null;
    }

    editPendingPartner(dist) {
        if (!dist.pendingPartnerData) return;
        const pd = dist.pendingPartnerData;
        const p = this.state.partnerModal;
        p.open = true;
        p.quotationId = dist.quotation_id;
        p.name = pd.supplier_name || '';
        p.nit = pd.nit || '';
        p.email = pd.email || '';
        p.phone = pd.phone || '';
        p.address = pd.address || '';
        p.cityId = pd.city_id || null;
        p.cityName = pd.city_name || '';
        p.cityInputText = '';
        p.cityDropdownOpen = false;
        p.cityDropdownItems = [];
        p.citySearching = false;
        p.categoryIds = (pd.categories || []).slice();
        p.catInputText = '';
        p.catDropdownOpen = false;
        p.catDropdownItems = [];
        p.submitting = false;
        p.error = null;
    }

    closePartnerPanel() {
        this.state.partnerModal.open = false;
        this.state.partnerModal.error = null;
    }

    // ── Dirección de entrega de la SDC ────────────────────────────────────────

    openDeliveryPanel() {
        const dd = this.state.deliveryData || {};
        const dm = this.state.deliveryModal;
        dm.name    = dd.name    || '';
        dm.email   = dd.email   || '';
        dm.phone   = dd.phone   || '';
        dm.address = dd.address || '';
        dm.error   = null;
        dm.open    = true;
    }

    closeDeliveryPanel() {
        this.state.deliveryModal.open  = false;
        this.state.deliveryModal.error = null;
    }

    get deliveryDisplayName() {
        if (this.state.deliveryModal.open) {
            return this.state.deliveryModal.name || '';
        }
        return this.state.deliveryData ? (this.state.deliveryData.name || '') : '';
    }

    onDeliveryFieldChange(field, ev) {
        this.state.deliveryModal[field] = ev.target.value;
    }

    onDeliveryPhoneInput(ev) {
        const digits = ev.target.value.replace(/\D/g, '').slice(0, 10);
        this.state.deliveryModal.phone = digits;
        ev.target.value = digits;
    }

    onSaveDelivery() {
        const dm = this.state.deliveryModal;
        dm.error = null;
        if (!(dm.name || '').trim())    { dm.error = 'El nombre es obligatorio.';   return; }
        const emailVal = (dm.email || '').trim();
        if (emailVal && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal)) {
            dm.error = 'Correo inválido.'; return;
        }
        const phone = (dm.phone || '').trim();
        if (!phone)                     { dm.error = 'El teléfono es obligatorio.'; return; }
        if (!/^\d{7,10}$/.test(phone))  { dm.error = 'El teléfono debe tener entre 7 y 10 dígitos.'; return; }
        if (!(dm.address || '').trim()) { dm.error = 'La dirección es obligatoria.'; return; }

        this.state.deliveryData = {
            name:    dm.name.trim(),
            email:   dm.email.trim(),
            phone,
            address: dm.address.trim(),
        };
        this.notification.add('Dirección de entrega guardada.', { type: 'info' });
        this.closeDeliveryPanel();
    }

    onPartnerFieldChange(field, ev) {
        this.state.partnerModal[field] = ev.target.value;
    }

    onPhoneInput(ev) {
        const digits = ev.target.value.replace(/\D/g, '').slice(0, 10);
        this.state.partnerModal.phone = digits;
        ev.target.value = digits;
    }

    onNitInput(ev) {
        // Allow only digits, dots and dash; auto-format as XXX.XXX.XXX-X
        const raw = ev.target.value.replace(/[^\d]/g, '').slice(0, 10);
        let fmt = raw;
        if (raw.length > 9) {
            fmt = raw.slice(0, 3) + '.' + raw.slice(3, 6) + '.' + raw.slice(6, 9) + '-' + raw.slice(9);
        } else if (raw.length > 6) {
            fmt = raw.slice(0, 3) + '.' + raw.slice(3, 6) + '.' + raw.slice(6);
        } else if (raw.length > 3) {
            fmt = raw.slice(0, 3) + '.' + raw.slice(3);
        }
        this.state.partnerModal.nit = fmt;
        ev.target.value = fmt;
    }

    // City Many2one dropdown
    onCityMousedown() {
        const p = this.state.partnerModal;
        p.cityDropdownOpen = true;
        if (!p.cityDropdownItems.length) this._loadCityItems('', p.stateId);
    }

    onCityBlur() {
        setTimeout(() => { this.state.partnerModal.cityDropdownOpen = false; }, 200);
    }

    onCityInput(ev) {
        const p = this.state.partnerModal;
        p.cityInputText = ev.target.value;
        p.cityDropdownOpen = true;
        clearTimeout(this._citySearchTimer);
        this._citySearchTimer = setTimeout(() => {
            this._loadCityItems(p.cityInputText.trim(), p.stateId);
        }, 300);
    }

    onCityKeydown(ev) {
        if (ev.key === 'Escape') {
            this.state.partnerModal.cityDropdownOpen = false;
            clearTimeout(this._citySearchTimer);
        }
    }

    selectCity(city) {
        const p = this.state.partnerModal;
        p.cityId = city.id;
        p.cityName = city.name;
        p.cityInputText = '';
        p.cityDropdownOpen = false;
        p.cityDropdownItems = [];
    }

    clearCity() {
        const p = this.state.partnerModal;
        p.cityId = null;
        p.cityName = '';
        p.cityInputText = '';
        p.cityDropdownOpen = false;
        p.cityDropdownItems = [];
    }

    async _loadCityItems(term, stateId) {
        const p = this.state.partnerModal;
        p.citySearching = true;
        try {
            const result = await rpc('/purchase_management/search_cities', {
                search_term: term,
                state_id: stateId || null,
                limit: 10,
            });
            p.cityDropdownItems = result.error ? [] : (result.cities || []).map(c => ({
                id: c.id, name: c.name, stateId: c.state_id, stateName: c.state_name,
            }));
        } catch (_) {
            p.cityDropdownItems = [];
        } finally {
            p.citySearching = false;
        }
    }

    getCityDropdownStyle() {
        return this._fixedDropdownStyle(document.querySelector('[data-dd-pcity]'));
    }

    // Category multi-select
    onCatMousedown() {
        const p = this.state.partnerModal;
        p.catDropdownOpen = true;
        p.catDropdownItems = this._availableCats(p.catInputText);
    }
    onCatBlur() {
        setTimeout(() => { this.state.partnerModal.catDropdownOpen = false; }, 200);
    }
    onCatInput(ev) {
        const p = this.state.partnerModal;
        p.catInputText = ev.target.value;
        p.catDropdownOpen = true;
        p.catDropdownItems = this._availableCats(p.catInputText);
    }
    onCatKeydown(ev) {
        if (ev.key === 'Escape') this.state.partnerModal.catDropdownOpen = false;
    }
    selectCat(cat) {
        const p = this.state.partnerModal;
        if (!p.categoryIds.some((c) => c.id === cat.id)) {
            p.categoryIds.push({ id: cat.id, name: cat.name });
        }
        p.catInputText = '';
        p.catDropdownItems = this._availableCats('');
    }
    removeCategory(catId) {
        const cats = this.state.partnerModal.categoryIds;
        const idx = cats.findIndex((c) => c.id === catId);
        if (idx >= 0) cats.splice(idx, 1);
    }
    getCatDropdownStyle() {
        return this._fixedDropdownStyle(document.querySelector('[data-dd-pcat]'));
    }
    _availableCats(term) {
        const selected = new Set(this.state.partnerModal.categoryIds.map((c) => c.id));
        let list = this.state.categories.filter((c) => !selected.has(c.id));
        if (term && term.trim()) {
            const t = term.trim().toLowerCase();
            list = list.filter((c) => c.name.toLowerCase().includes(t));
        }
        return list;
    }

    async onSavePartner() {
        const p = this.state.partnerModal;

        // Validaciones
        if (!(p.name || '').trim()) { p.error = 'El nombre es obligatorio.'; return; }
        const nit = (p.nit || '').trim();
        if (!nit) { p.error = 'El NIT es obligatorio.'; return; }
        if ((nit.match(/\./g) || []).length < 2 || !/^\d/.test(nit) || !/\d$/.test(nit)) {
            p.error = 'NIT inválido. Formato esperado: 900.123.456-7'; return;
        }
        if (!(p.email || '').trim()) { p.error = 'El correo electrónico es obligatorio.'; return; }
        const phone = (p.phone || '').trim();
        if (!phone) { p.error = 'El teléfono es obligatorio.'; return; }
        if (!/^\d{10}$/.test(phone)) { p.error = `El teléfono debe tener exactamente 10 dígitos (ingresaste ${phone.length}).`; return; }
        if (!(p.address || '').trim()) { p.error = 'La dirección es obligatoria.'; return; }
        if (!p.cityId) { p.error = 'La ciudad es obligatoria.'; return; }
        if (!p.categoryIds.length) { p.error = 'Selecciona al menos una categoría.'; return; }

        p.submitting = true;
        p.error = null;
        try {
            // Verificar NIT duplicado antes de guardar
            const check = await rpc('/purchase_management/check_nit', { nit });
            if (check.exists) {
                p.error = `El NIT ${nit} ya está registrado para "${check.partner_name}".`;
                return;
            }

            // Guardar datos en TODAS las distribuciones con el mismo quotation_id
            // (el mismo proveedor puede aparecer en múltiples productos)
            const pendingData = {
                quotation_id: p.quotationId,
                supplier_name: p.name.trim(),
                nit: nit,
                email: p.email.trim(),
                phone: phone,
                address: p.address.trim(),
                city_id: p.cityId,
                city_name: p.cityName,
                categories: p.categoryIds.slice(),
                category_ids: p.categoryIds.map((c) => c.id),
            };
            for (const line of this.state.lines) {
                for (const dist of line.distributions) {
                    if (dist.quotation_id === p.quotationId) {
                        dist.partnerFound = true;
                        dist.pendingPartnerData = pendingData;
                    }
                }
            }
            this.notification.add(
                `Datos de "${p.name.trim()}" guardados. El proveedor se creará al confirmar.`,
                { type: 'info' }
            );
            this.closePartnerPanel();
        } catch (e) {
            p.error = 'Error al verificar el NIT: ' + (e.message || String(e));
        } finally {
            p.submitting = false;
        }
    }

    // Actions

    async onConfirm() {
        if (!this.allMapped) {
            // Resaltar líneas no vinculadas navegando a la primera
            const firstUnmapped = this.state.lines.findIndex((l) => !this.isMapped(l));
            if (firstUnmapped >= 0) this.state.wizardIndex = firstUnmapped;
            this.notification.add(
                "Debe vincular todos los productos con una variante de bodega antes de confirmar.",
                { type: "warning" }
            );
            return;
        }

        // Validar distribuciones: ninguna línea puede superar la cantidad solicitada
        const overLines = this.state.lines.filter(
            (l) => l.distributions.length > 0 && this.getDistributionStatus(l) === 'over'
        );
        if (overLines.length > 0) {
            const names = overLines.map((l) => `"${l.name}"`).join(', ');
            this.notification.add(
                `La distribución de cantidades supera lo solicitado en: ${names}. Corrígelas antes de confirmar.`,
                { type: "danger" }
            );
            return;
        }

        // Validar que los productos con múltiples proveedores tengan distribución completa
        const partialLines = this.state.lines.filter(
            (l) => l.distributions.length > 1 && this.getDistributionStatus(l) === 'partial'
        );
        if (partialLines.length > 0) {
            const firstPartial = this.state.lines.findIndex(
                (l) => l.distributions.length > 1 && this.getDistributionStatus(l) === 'partial'
            );
            if (firstPartial >= 0) this.state.wizardIndex = firstPartial;
            this.notification.add(
                `Debe distribuir el total de unidades entre los proveedores en: ${partialLines.map((l) => `"${l.name}"`).join(', ')}.`,
                { type: "danger" }
            );
            return;
        }

        this.state.submitting = true;
        try {
            // Construir mappings con pending_creation cuando aplique
            const mappings = this.state.lines.map((l) => ({
                line_id: l.id,
                variant_id: l.pendingCreation ? null : l.selectedVariantId,
                pending_creation: l.pendingCreation || null,
                cost_center_id: l.costCenterId || null,
            }));

            // Construir distribuciones de todas las líneas que tienen proveedores adjudicados.
            // Con 1 solo proveedor: auto-asignar toda la qty (no requiere acción del usuario).
            // Con múltiples: usar los valores ingresados.
            const distributions = [];
            for (const l of this.state.lines) {
                if (l.distributions.length === 1) {
                    distributions.push({
                        line_id: l.id,
                        qline_id: l.distributions[0].qline_id,
                        assigned_qty: l.qty,
                    });
                } else if (l.distributions.length > 1) {
                    for (const d of l.distributions) {
                        distributions.push({
                            line_id: l.id,
                            qline_id: d.qline_id,
                            assigned_qty: d.assigned_qty || 0,
                        });
                    }
                }
            }

            // Recoger partners pendientes de crear (uno por distribución aún no creada)
            const seen = new Set();
            const pendingPartners = [];
            for (const l of this.state.lines) {
                for (const d of l.distributions) {
                    if (d.pendingPartnerData && !seen.has(d.quotation_id)) {
                        seen.add(d.quotation_id);
                        pendingPartners.push(d.pendingPartnerData);
                    }
                }
            }

            const result = await rpc("/purchase_management/create_and_confirm_mapping", {
                quotation_id: this.props.quotationId,
                mappings,
                distributions,
                pending_partners: pendingPartners,
                delivery_data: this.state.deliveryData || null,
            });

            if (result.error) {
                this.notification.add("Error: " + result.error, { type: "danger" });
            } else {
                const created = (result.created_variants || []);
                const newCount = created.filter((v) => !v.already_existed).length;
                const reutCount = created.filter((v) => v.already_existed).length;
                let msg = "Orden creada. Productos vinculados a bodega correctamente.";
                if (newCount > 0) msg += ` ${newCount} variante(s) nueva(s) creadas.`;
                if (reutCount > 0) msg += ` ${reutCount} variante(s) reutilizada(s).`;
                this.notification.add(msg, { type: "success" });
                this.props.onConfirmSuccess?.();
                this.props.close();
            }
        } catch (e) {
            this.notification.add(
                "Error al confirmar: " + (e.message || String(e)),
                { type: "danger" }
            );
        } finally {
            this.state.submitting = false;
        }
    }

    async onCancel() {
        // Avisar si hay variantes pendientes de crear que se perderán
        if (this.hasAnyPendingCreation) {
            const ok = window.confirm(
                'Tienes variantes pendientes de crear que se perderán si cancelas.\n¿Deseas salir sin guardar?'
            );
            if (!ok) return;
        }
        this.props.close();
    }
}

// Launcher widget — se coloca en la vista de formulario como <widget>

class ProductLinkingLauncher extends Component {
    static template = "purchase_management.ProductLinkingLauncher";
    static props = ["*"];

    setup() {
        this.dialog = useService("dialog");
    }

    openDialog() {
        const record = this.props.record;
        const quotationId = record.resId;
        this.dialog.add(ProductLinkingDialog, {
            quotationId,
            title: 'Odoo',
            onConfirmSuccess: async () => {
                await record.model.load({ resId: quotationId });
            },
        });
    }
}

registry.category("view_widgets").add("product_linking_launcher", {
    component: ProductLinkingLauncher,
});
