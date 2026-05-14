/**
 * Extends the list renderer to guard focus operations when the table element
 * is not yet available.
 */
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    focusCell(...args) {
        if (!this.tableRef?.el) {
            return;
        }
        return super.focusCell(...args);
    },
});
