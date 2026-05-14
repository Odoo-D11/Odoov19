/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

// =========================================================================
// HELPER: Comprueba si el usuario pertenece a Creador o Administrador
// =========================================================================

async function _checkContactsGroup() {
    const isCreator = await user.hasGroup("contacts_management.group_res_partner_creator");
    const isAdmin   = await user.hasGroup("contacts_management.group_res_partner_admin");
    return isCreator || isAdmin;
}

// =========================================================================
// LISTA — Controller + View
// =========================================================================

export class ContactsBannerListController extends ListController {
    setup() {
        super.setup();
        this.action = useService("action");
        this.state = useState({
            ...this.state,
            isCreatorOrAdmin: false,
        });

        onWillStart(async () => {
            this.state.isCreatorOrAdmin = await _checkContactsGroup();
        });
    }

    onClickImportContacts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Odoo",
            res_model: "contacts.bulk.import.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
        });
    }
}

ContactsBannerListController.template = "contacts_management.ContactsBannerListView";

export const contactsBannerListView = {
    ...listView,
    Controller: ContactsBannerListController,
    buttonTemplate: "contacts_management.ContactsBannerDropdownButton",
};

registry.category("views").add("contacts_banner_list_view", contactsBannerListView);

// =========================================================================
// KANBAN — Controller + View
// =========================================================================

export class ContactsBannerKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.action = useService("action");
        this.state = useState({
            ...this.state,
            isCreatorOrAdmin: false,
        });

        onWillStart(async () => {
            this.state.isCreatorOrAdmin = await _checkContactsGroup();
        });
    }

    onClickImportContacts() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Odoo",
            res_model: "contacts.bulk.import.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
        });
    }
}

export const contactsBannerKanbanView = {
    ...kanbanView,
    Controller: ContactsBannerKanbanController,
    buttonTemplate: "contacts_management.ContactsBannerKanbanButtons",
};

registry.category("views").add("contacts_banner_kanban_view", contactsBannerKanbanView);
