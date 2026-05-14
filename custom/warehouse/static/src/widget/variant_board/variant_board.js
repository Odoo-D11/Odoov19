/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount, onWillUpdateProps, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";


class WarehouseVariantBoardWidget extends Component {
    static template = "warehouse.WarehouseVariantBoardWidget";
    static supportedTypes = ["one2many"];

    setup() {
        super.setup();
        this.isDestroyed = false;
        this.loadVersion = 0;
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            variants: [],
            loading: false,
        });

        this.productId = this.props.record.resId || this.props.record._config?.resId || false;
        this.modelName = this.props.record.resModel || "warehouse.product";
        this._cachedPopupViewId = undefined;
        this.variantLineKey = JSON.stringify(
            this.props.record.data.variant_ids?.resIds || []
        );

        onWillStart(async () => {
            if (this.productId) {
                await this.fetchVariants();
            }
        });

        onWillUpdateProps(async (nextProps) => {
            const newKey = JSON.stringify(
                nextProps.record.data.variant_ids?.resIds || []
            );
            const newProductId = nextProps.record.resId || nextProps.record._config?.resId || false;

            if (newKey !== this.variantLineKey || newProductId !== this.productId) {
                this.variantLineKey = newKey;
                this.productId = newProductId;
                this.state.variants = [];
                if (this.productId) {
                    await this.fetchVariants({ props: nextProps });
                }
            }
        });

        onWillUnmount(() => {
            this.isDestroyed = true;
        });
    }

    async fetchVariants({ props = this.props } = {}) {
        const loadVersion = ++this.loadVersion;
        const productId = props.record.resId || props.record._config?.resId || false;
        if (!productId) {
            this.state.variants = [];
            return;
        }

        this.state.loading = true;
        try {
            const variants = await this.orm.searchRead(
                "warehouse.product.variant",
                [["product_id", "=", productId]],
                ["id", "name", "estimated_price", "currency_id"]
            );

            if (this.isDestroyed || loadVersion !== this.loadVersion) {
                return;
            }

            if (productId !== (this.props.record.resId || this.props.record._config?.resId)) {
                return;
            }

            this.state.variants = variants;
            await this.syncVariantLineRecords(variants, { props });
        } catch (error) {
            if (this.isDestroyed || loadVersion !== this.loadVersion) return;
            console.error("Error al cargar las variantes", error);
            this.notification.add(
                _t("No se pudieron cargar las variantes. Intenta nuevamente."),
                { type: "danger" }
            );
        } finally {
            if (!this.isDestroyed && loadVersion === this.loadVersion) {
                this.state.loading = false;
            }
        }
    }

    async syncVariantLineRecords(variants, { props = this.props } = {}) {
        const record = props.record;
        if (!record || !record.resId || this.__owl__?.status === "destroyed") {
            return;
        }

        const variantLineList = record.data?.variant_ids;
        if (!variantLineList || typeof variantLineList._replaceWith !== "function") {
            return;
        }

        const editedRecord = variantLineList.editedRecord;
        const isInlineEditActive = Boolean(
            editedRecord && (editedRecord.dirty || !editedRecord.resId)
        );
        if (isInlineEditActive) {
            return;
        }

        const ids = variants.map(v => v.id);
        const currentIds = variantLineList._currentIds || [];
        const sameLength = ids.length === currentIds.length;
        const sameOrder = sameLength && ids.every((id, idx) => id === currentIds[idx]);
        if (sameOrder) {
            return;
        }

        try {
            await variantLineList._replaceWith(ids);
        } catch (error) {
            console.error("Error sincronizando variantes:", error);
        }
    }

    getTotalCount() {
        return this.state.variants.length;
    }

    getUnitsText() {
        return this.getTotalCount() === 1
            ? "Variante registrada"
            : "Variantes registradas";
    }

    get showAddButton() {
        return this.state.variants.length === 0;
    }

    async getPopupViewId() {
        if (this._cachedPopupViewId !== undefined) {
            return this._cachedPopupViewId;
        }
        try {
            const viewId = await this.orm.call(
                this.modelName,
                "get_variant_popup_view_id",
                []
            );
            this._cachedPopupViewId = viewId;
            return viewId;
        } catch {
            this._cachedPopupViewId = false;
            return false;
        }
    }

    async openVariantManager() {
        const productId = this.props.record.resId || this.props.record._config?.resId || false;
        if (!productId) {
            this.notification.add(
                _t("Para gestionar variantes, primero debes guardar el producto."),
                { type: "danger" }
            );
            return;
        }

        try {
            const viewId = await this.getPopupViewId();

            const refreshVariants = async () => {
                await new Promise(resolve => setTimeout(resolve, 200));
                await this.fetchVariants();
            };

            await this.actionService.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: this.modelName,
                    view_mode: "form",
                    views: [[viewId || false, "form"]],
                    view_id: viewId || false,
                    target: "new",
                    res_id: productId,
                    name: "Odoo",
                },
                { onClose: refreshVariants }
            );
        } catch (error) {
            console.error("Error abriendo el gestor de variantes", error);
            this.notification.add(
                _t("No se pudo abrir la gestión de variantes. Intenta nuevamente."),
                { type: "danger" }
            );
        }
    }

    async deleteAllVariants() {
        this.dialog.add(ConfirmationDialog, {
            body: "¿Está seguro de que desea eliminar todas las variantes de este producto?",
            confirm: async () => {
                try {
                    const variantIds = this.state.variants.map(v => v.id);
                    await this.orm.unlink("warehouse.product.variant", variantIds);
                    await this.fetchVariants();
                    this.notification.add(
                        "Variantes eliminadas correctamente",
                        { type: "success" }
                    );
                } catch (error) {
                    this.notification.add(
                        "Error al eliminar las variantes",
                        { type: "danger" }
                    );
                    console.error("Error deleting variants:", error);
                }
            },
            cancel: () => {},
        });
    }

    getEmptyStateDescription() {
        return markup(
            `Las <strong>variantes</strong> representan las distintas versiones comerciales de este producto: diferentes marcas, modelos, referencias o configuraciones que comparten la misma categoría pero se identifican y cotizan de forma independiente. Usa el botón <strong><i class="fa fa-plus"></i></strong> para registrar la primera variante.`
        );
    }
}

registry.category("fields").add("VariantBoard", {
    component: WarehouseVariantBoardWidget,
    displayName: "Widget de variantes de producto",
    supportedTypes: WarehouseVariantBoardWidget.supportedTypes,
});
