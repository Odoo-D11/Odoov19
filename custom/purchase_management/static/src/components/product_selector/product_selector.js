/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const ACTION_TAG = "purchase_management_product_selector";

export class PurchaseManagementProductSelector extends Component {
    static template = "purchase_management.ProductSelector";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.storageKey = "pm_product_selector_state";

        const resolveRecordState = () => {
            const params = this.props.action.params || {};
            const rfqId = params.request_quotation_id || null;

            if (rfqId) {
                const state = { id: rfqId };
                sessionStorage.setItem(this.storageKey, JSON.stringify(state));
                return state;
            }
            const stored = sessionStorage.getItem(this.storageKey);
            if (stored) {
                try {
                    const parsed = JSON.parse(stored);
                    return { id: parseInt(parsed.id, 10) };
                } catch (_) { /* ignore */ }
            }
            return { id: null };
        };

        const recordState = resolveRecordState();
        this.recordId = recordState.id;
        this.rfqId = this.recordId;

        this.state = useState({
            // General
            loading: true,
            error: null,
            reference: "",
            subject: "",
            typeName: "",
            userName: "",
            userEmail: "",

            // Productos
            products: [],
            selectedProducts: new Set(),
            searchQuery: "",
            currentPage: 1,
            itemsPerPage: 25,
        });

        onWillStart(async () => {
            if (!this.recordId) {
                this.state.error = "No se pudo determinar la Solicitud.";
                this.state.loading = false;
                return;
            }
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const productsData = await rpc("/purchase_management/get_products_for_supplier", {
                request_quotation_id: this.recordId,
            });

            if (productsData.error) throw new Error(productsData.error);

            this.state.reference = productsData.reference;
            this.state.subject = productsData.subject;
            this.state.products = productsData.products;
            this.state.typeName = productsData.type_name || "Productos";
            this.state.userName = productsData.user_name || "";
            this.state.userEmail = productsData.user_email || "";
        } catch (error) {
            this.state.error = error.message;
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    get filteredProducts() {
        if (!this.state.searchQuery) return this.state.products;
        const query = this.state.searchQuery.toLowerCase();
        return this.state.products.filter(p =>
            p.name.toLowerCase().includes(query)
        );
    }

    get paginatedProducts() {
        const start = (this.state.currentPage - 1) * this.state.itemsPerPage;
        return this.filteredProducts.slice(start, start + this.state.itemsPerPage);
    }

    get totalPages() {
        return Math.ceil(this.filteredProducts.length / this.state.itemsPerPage);
    }

    get selectedCount() {
        return this.state.selectedProducts.size;
    }

    get inputSelectedValue() {
        const suffix = this.state.selectedProducts.size === 1 ? "Seleccionado" : "Seleccionados";
        return `Prod. ${suffix}`;
    }

    get allSelected() {
        return this.filteredProducts.length > 0 &&
            this.filteredProducts.every(p => this.state.selectedProducts.has(p.id));
    }

    get productsWithSpecification() {
        return this.state.products.filter(p => p.specification && p.specification.trim()).length;
    }

    get alreadySentCount() {
        return this.state.products.filter(p => p.sent_to_emails && p.sent_to_emails.trim()).length;
    }

    get sentProducts() {
        return this.state.products.filter(p => p.sent_to_emails && p.sent_to_emails.trim());
    }

    truncateText(text, maxLength = 40) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    getSuppliersTooltip(product) {
        if (!product.sent_to_emails) return '';
        return 'Enviado a: ' + product.sent_to_emails;
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
        this.state.currentPage = 1;
    }

    toggleProduct(productId) {
        if (this.state.selectedProducts.has(productId)) {
            this.state.selectedProducts.delete(productId);
        } else {
            this.state.selectedProducts.add(productId);
        }
        this.state.selectedProducts = new Set(this.state.selectedProducts);
    }

    toggleSelectAll() {
        if (this.allSelected) {
            this.filteredProducts.forEach(p => this.state.selectedProducts.delete(p.id));
        } else {
            this.filteredProducts.forEach(p => this.state.selectedProducts.add(p.id));
        }
        this.state.selectedProducts = new Set(this.state.selectedProducts);
    }

    changePage(delta) {
        const newPage = this.state.currentPage + delta;
        if (newPage >= 1 && newPage <= this.totalPages) {
            this.state.currentPage = newPage;
        }
    }

    isProductSelected(productId) {
        return this.state.selectedProducts.has(productId);
    }

    /**
     * Genera la plantilla HTML del correo con los productos seleccionados.
     * Renderización en cliente para mayor velocidad.
     */
    _generateEmailTemplate() {
        const selectedIds = this.state.selectedProducts;
        const selectedProducts = this.state.products.filter(p => selectedIds.has(p.id));

        // Determinar el tipo de elementos
        let itemsLabel = "Productos";
        if (this.state.typeName === "Servicios") {
            itemsLabel = "Servicios";
        } else if (this.state.typeName === "Mixtos") {
            itemsLabel = "Elementos";
        }

        // Calcular fecha límite (3 días desde hoy)
        const deadline = new Date();
        deadline.setDate(deadline.getDate() + 3);
        const deadlineStr = deadline.toLocaleDateString('es-CO', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });

        // Formatear cantidad con separador de miles
        const formatQty = (qty) => {
            return Math.floor(qty).toLocaleString('es-CO');
        };

        // Generar filas de productos con sus especificaciones
        let productRows = '';
        for (const product of selectedProducts) {
            // Fila del producto
            productRows += `
                <tr>
                    <td style="border-bottom:1px solid #4d4d4d;border-right:1px solid #4d4d4d;padding:4px 8px;">
                        ${product.name || '—'}
                    </td>
                    <td style="border-bottom:1px solid #4d4d4d;border-right:1px solid #4d4d4d;padding:4px 8px;text-align:center;">
                        ${formatQty(product.qty)}
                    </td>
                    <td style="border-bottom:1px solid #4d4d4d;padding:4px 8px;text-align:center;">
                        ${product.uom || '—'}
                    </td>
                </tr>`;

            // Fila de especificación/nota si existe
            if (product.specification && product.specification.trim()) {
                productRows += `
                <tr>
                    <td colspan="3" style="border-bottom:1px solid #4d4d4d;padding:4px 8px;background-color:#f5f5f5;font-style:italic;">
                        ${product.specification}
                    </td>
                </tr>`;
            }
        }

        // Plantilla completa
        return `
            <div style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;color:#222;">
                <p style="font-size:13px;margin:0 0 10px 0;line-height:1.45;">
                    Estimado proveedor.
                </p>
                <p style="font-size:13px;margin:0 0 14px 0;line-height:1.5;">
                    Por medio del presente nos permitimos solicitar su cotización para la solicitud
                    <strong>${this.state.reference}</strong> correspondiente a: <strong>${this.state.subject}.</strong>
                    Agradecemos nos haga llegar su mejor oferta comercial considerando los productos detallados a continuación,
                    antes de la fecha límite: <strong>${deadlineStr}.</strong>
                </p>
                <table style="width:100%;border-collapse:collapse;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.35;border-style:solid;border-color:#4d4d4d;border-width:1px 1px 0 1px;color:#000;">
                    <thead>
                        <tr>
                            <td colspan="3" style="padding:5px 8px;text-align:center;text-transform:uppercase;letter-spacing:.06em;font-weight:700;border-bottom:1px solid #4d4d4d;">
                                ${itemsLabel} solicitados
                            </td>
                        </tr>
                        <tr>
                            <th style="border-top:1px solid #4d4d4d;border-bottom:1px solid #4d4d4d;border-right:1px solid #4d4d4d;padding:5px 8px;text-align:left;font-weight:700;width:60%;">
                                Nombre
                            </th>
                            <th style="border-top:1px solid #4d4d4d;border-bottom:1px solid #4d4d4d;border-right:1px solid #4d4d4d;padding:5px 8px;text-align:center;font-weight:700;width:20%;">
                                Cantidad
                            </th>
                            <th style="border-top:1px solid #4d4d4d;border-bottom:1px solid #4d4d4d;padding:5px 8px;text-align:center;font-weight:700;width:20%;">
                                Unidad de Medida
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        ${productRows}
                    </tbody>
                </table>
                <p style="font-size:13px;margin:18px 0 0 0;line-height:1.45;">
                    Agradecemos confirmar la recepción de esta solicitud. Para cualquier duda, aclaración o
                    requerimiento de información adicional sobre las especificaciones técnicas de los productos,
                    por favor no dude en contactarnos. Quedamos atentos a su pronta respuesta y esperamos
                    contar con su mejor propuesta comercial.
                </p>
                <p style="font-size:13px;margin:18px 0 0 0;line-height:1.45;color:#000000;">
                    <strong>Nota:</strong> Junto con este correo se adjunta un <strong>formato
                    de cotización</strong> que deberá ser <strong>diligenciado y remitido como
                            parte de su respuesta</strong>. Este documento es de <strong>carácter
                    obligatorio</strong> para la evaluación de su oferta, por lo que agradecemos
                    completarlo con toda la información solicitada y adjuntarlo al momento de
                    remitir su cotización. </p> <br/>
                    Cordialmente,<br/>
                    <strong>${this.state.userName} | ${this.state.userEmail}</strong>
            </div>`;
    }

    async openSendMailModal() {
        if (this.state.selectedProducts.size === 0) {
            this.notification.add("Debe seleccionar al menos un producto", { type: "warning" });
            return;
        }

        try {
            // Generar plantilla en cliente (más rápido que llamar al servidor)
            const emailBody = this._generateEmailTemplate();
            const selectedProductIds = Array.from(this.state.selectedProducts);

            // Crear el Excel con los productos seleccionados
            const excelResponse = await rpc("/purchase_management/create_excel_for_selected_products", {
                request_quotation_id: this.recordId,
                product_ids: selectedProductIds,
            });

            if (excelResponse.error) {
                throw new Error(excelResponse.error);
            }

            await this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: 'purchase.send.mail.wizard',
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    default_request_quotation_id: this.recordId,
                    default_type: 'rfq_to_supplier',
                    default_body: emailBody,
                    default_subject: this.state.subject,
                    default_attachment_ids: [[6, 0, [excelResponse.attachment_id]]],
                    default_selected_product_line_ids: [[6, 0, selectedProductIds]],
                }
            }, {
                onClose: async () => {
                    // Recargar datos cuando se cierre el wizard para reflejar los cambios
                    this.state.selectedProducts = new Set();
                    await this.loadData();
                }
            });
        } catch (error) {
            console.error("Error abriendo el wizard de envio de productos", error);
            this.notification.add("No se pudo abrir el wizard de envío de productos. Intenta nuevamente.",
                { type: "danger" }
            );
        }
    }

    async goBack() {
        const currentController = this.actionService.currentController;

        try {
            await this.actionService.doAction({ type: 'ir.actions.act_window_close' });
            if (this.actionService.currentController &&
                this.actionService.currentController.jsId === currentController.jsId) {
                await this.actionService.restore();
            }

        } catch (error) {
            console.warn("Fallo al intentar volver, redirigiendo al menú principal...");
            await this.actionService.doAction("purchase_management.action_view_request_quotation", { clear_breadcrumbs: true });
        }
    }
}

registry.category("actions").add(ACTION_TAG, PurchaseManagementProductSelector);
