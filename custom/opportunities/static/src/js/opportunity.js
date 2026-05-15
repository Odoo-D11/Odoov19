/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";
import { useState, onMounted, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";

// ——— CONSTS —————————————————————————————————————————————————————————————————
const COLORS = ["#1abc9c", "#2ecc71",
    "#3498db", "#9b59b6", "#e67e22",
    "#e74c3c", "#f1c40f", "#34495e",
    "#16a085", "#27ae60", "#2980b9",
    "#8e44ad", "#d35400", "#c0392b",
    "#f39c12", "#7f8c8d"];
let ci = 0;
const getRandomColor = () => COLORS[ci++ % COLORS.length];

const STAGE_MAP = {
    draft: "Borrador", open: "Abierto", paused: "En pausa",
    in_pre_sale: "En preventa", pte_approval_pre_sale_leader: "Pte. por aprobación",
    pte_approval_manager: "Pte. por aprobación", pte_upload_offer: "En preventa",
    pte_present: "Pte. por presentar", presented: "Presentado",
    won: "Ganado", lost: "Perdido", cancelled: "Cancelado"
};
const STATE_MAP = {
    unnasigned: "Sin asignar", in_management: "En gestión",
    paused: "En pausa", delivered: "Entregado",
    not_feasible: "No viable", cancelled: "Cancelado"
};
const STATUS_ORDER = [
    "Sin asignar",
    "Entregado",
    "En gestión",
    "En pausa",
    "No viable",           
    "Ganado",
    "Perdido - Cancelado"
];
const STATUS_ICONS = {
    "Sin asignar": "fa fa-minus-circle",
    "En gestión": "fa fa-tasks",
    "En pausa": "fa fa-clock-o",
    "Entregado": "fa fa-check-circle",
    "No viable": "fa fa-times-circle", 
    "Ganado": "fa fa-trophy",
    "Perdido - Cancelado": "fa fa-trash",
};
const STATUS_COLORS = {
    "Sin asignar": "#95a5a6",
    "En gestión": "#3498db",
    "En pausa": "#f39c12",
    "Entregado": "#27ae60",
    "No viable": "#e74c8c",             
    "Ganado": "#ffd700",
    "Perdido - Cancelado": "#000000",
};
const FIELD_MAP = {
    "En gestión": ["stage_pre_sale", "in_management"],
    "En pausa": ["stage_pre_sale", "paused"],
    "No viable": ["stage_pre_sale", "not_feasible"],
    "Ganado": ["stage", "won"]
};

// ——— CONTROLLER —————————————————————————————————————————————————————————————

class OpportunityDropdownListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            presales: [], statuses: [], selectedPresaleId: null,
            selectedStatusName: null, showArchived: false, hasPermission: false,
            loading: false,
        });
        this._searchSyncInterval = setInterval(() => {
            const sm = this.env.searchModel;
            if (!sm) return;
            const activePresale = sm.getSearchItems(f => f.isFromPreSaleList && f.isActive);
            if (!activePresale.length && this.state.selectedPresaleId) {
                this.state.selectedPresaleId = null;
            }
            const activeStatus = sm.getSearchItems(f => f.isFromStatusList && f.isActive);
            if (!activeStatus.length && this.state.selectedStatusName) {
                this.state.selectedStatusName = null;
            }
        }, 500);
        onWillUnmount(() => clearInterval(this._searchSyncInterval));
        document.addEventListener("show.bs.dropdown", this.onDropdownShow);
        document.addEventListener("hide.bs.dropdown", this.onDropdownHide);
        onMounted(() => this.init());
    }

    async init() {
        const users = await this.orm.searchRead(
            "res.users",
            [["id", "=", this.props.context.uid]],
            ["group_ids"]
        );
        const userGroups = users[0]?.group_ids || [];
        const groups = await this.orm.searchRead(
            "res.groups",
            [["comment", "=", "Permisos de lider preventa"]],
            ["id"],
            { limit: 1 }
        );
        const permisoPreventaGroupId = groups[0]?.id;
        this.state.hasPermission = permisoPreventaGroupId
            ? userGroups.includes(permisoPreventaGroupId)
            : false;
        if (this.state.hasPermission) {
            this.state.loading = true;
            await Promise.all([this.loadPresales(), this.loadStatuses()]);
            this.state.loading = false;
        }
    }

    _clearSidebarFilters() {
        const sm = this.env.searchModel;
        sm && sm.getSearchItems(f => f.isFromPreSaleList || f.isFromStatusList)
            .filter(f => f.isActive).forEach(f => sm.toggleSearchItem(f.id));
    }

    _clearDefaultFilters() {
        const sm = this.env.searchModel;
        if (!sm) return;
        sm.getSearchItems(f => f.isDefault && f.isActive)
            .forEach(f => sm.toggleSearchItem(f.id));
    }

    toggleArchived() {
        this.state.showArchived = !this.state.showArchived;
        this._clearSidebarFilters();
        this.state.loading = true;
        Promise.all([this.loadPresales(), this.loadStatuses()]).then(() => {
            this.state.loading = false;
            if (this.state.selectedPresaleId) {
                const presale = this.state.presales.find(p => p.id === this.state.selectedPresaleId);
                if (presale) {
                    this.filterByPersonal(presale);
                    return;
                }
                this.state.selectedPresaleId = null;
            }
            if (this.state.selectedStatusName) {
                const status = this.state.statuses.find(s => s.name === this.state.selectedStatusName);
                if (status) {
                    this.filterByStatus(status);
                    return;
                }
                this.state.selectedStatusName = null;
            }
            this.model.root.load({ domain: [] });
        });
    }

    async loadPresales() {
        const lines = await this.orm.searchRead("opportunity.team.assignment.line",
            [["team_id.name", "ilike", "Preventa"]], ["member_id", "assignment_id"]);
        if (!lines.length) return this.state.presales = [];
        const aIds = lines.map(l => l.assignment_id[0]);
        const assigns = await this.orm.searchRead("opportunity.team.assignment", [["id", "in", aIds]], ["id", "lead_id"]);
        const leadMap = Object.fromEntries(assigns.map(a => [a.id, a.lead_id[0]]));
        const domain = [["id", "in", Object.values(leadMap)]];
        domain.push(this.state.showArchived ? ["active", "in", [true, false]] : ["active", "=", true]);
        const leads = await this.orm.searchRead("opportunity", domain, ["id", "type"]);
        const typeMap = Object.fromEntries(leads.map(l => [l.id, l.type]));
        const byUser = {};
        lines.forEach(({ member_id: [uid, name], assignment_id: [aid] }) => {
            const leadId = leadMap[aid];
            if (!typeMap[leadId]) return;
            const tp = typeMap[leadId];
            byUser[uid] = byUser[uid] || { id: uid, name, count: 0, types: {}, color: getRandomColor() };
            byUser[uid].count++;
            byUser[uid].types[tp] = (byUser[uid].types[tp] || 0) + 1;
        });
        this.state.presales = Object.values(byUser).map(u => ({
            ...u,
            types: Object.entries(u.types).map(([t, c]) => ({ type: t, count: c }))
        }));
    }

    async loadStatuses() {
        const domain = this.state.showArchived ? [["active", "in", [true, false]]] : [["active", "=", true]];
        const opps = await this.orm.searchRead("opportunity", domain, ["stage_pre_sale", "stage", "type"]);
        const counts = opps.reduce((acc, { stage_pre_sale, stage, type }) => {
            let ps = (stage_pre_sale === "unnasigned" && type === "pipeline") ? "in_pre_sale" : stage_pre_sale;
            if (ps === "in_pre_sale") return acc;
            if (stage) {
                const s = STAGE_MAP[stage] || stage;
                if (s === "Ganado" || ["Perdido", "Cancelado"].includes(s)) {
                    const key = s === "Ganado" ? "Ganado" : "Perdido - Cancelado";
                    acc[key] = acc[key] || { name: key, count: 0 };
                    acc[key].count++;
                    return acc;
                }
            }
            const st = STATE_MAP[ps] || ps;
            acc[st] = acc[st] || { name: st, count: 0 };
            acc[st].count++;
            return acc;
        }, {});
        this.state.statuses = Object.values(counts)
            .filter(s => s.count > 0)
            .map(s => ({
                ...s,
                icon: STATUS_ICONS[s.name] || "fa fa-question-circle",
                color: STATUS_COLORS[s.name] || "#7f8c8d",
            }))
            .sort((a, b) => STATUS_ORDER.indexOf(a.name) - STATUS_ORDER.indexOf(b.name));

    }

    filterByPersonal = personal => {
        this._clearDefaultFilters();
        this._clearSidebarFilters();
        this.state.selectedPresaleId = personal.id; this.state.selectedStatusName = null;
        const domain = [
            ["assignment_ids.member_id.employee_id.name", "ilike", personal.name],
            ...(this.state.showArchived ? [["active", "in", [true, false]]] : [["active", "=", true]])
        ];
        this.env.searchModel.createNewFilters([{ description: `Asignado a: ${personal.name}`, domain, isFromPreSaleList: true }]);
    }

    filterByStatus = status => {
        this._clearDefaultFilters();
        this._clearSidebarFilters();
        this.state.selectedStatusName = status.name;
        this.state.selectedPresaleId = null;
        let dom;
        if (status.name === "Perdido - Cancelado") {
            dom = [["stage", "in", ["lost", "cancelled"]]];
        } else if (status.name === "Entregado") {
            dom = [
                ["stage_pre_sale", "=", "delivered"],
                ["stage", "not in", ["won", "lost", "cancelled"]],
            ];
        } else if (status.name === "Sin asignar") {
            dom = [
                ["stage", "=", "in_pre_sale"],
                "|",
                ["type", "=", "pipeline"],
                ["stage_pre_sale", "=", "unnasigned"],
            ];
        } else {
            const [f, v] = FIELD_MAP[status.name] || ["stage", status.name.toLowerCase()];
            dom = [[f, "=", v]];
        }
        dom.push(
            this.state.showArchived
                ? ["active", "in", [true, false]]
                : ["active", "=", true]
        );
        this.env.searchModel.createNewFilters([{
            description: `Estado: ${status.name}`,
            domain: dom,
            isFromStatusList: true,
        }]);
    }

    // === Acciones de oportunidad ===

    actionCreateNewLead() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "opportunity",
            views: [[false, "form"]],
            target: "current",
        });
    }

    actionCreateNewActivity() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Actividades",
            res_model: "opportunity.activity",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    onDropdownShow = ev => ev.target.closest(".btn-group")?.querySelector(".dropdown-toggle-anim .dropdown-icon")?.classList.add("rotate-up");
    onDropdownHide = ev => ev.target.closest(".btn-group")?.querySelector(".dropdown-toggle-anim .dropdown-icon")?.classList.remove("rotate-up");
}

OpportunityDropdownListController.template = "LeaderPreSaleListController";
registry.category("views").add("opportunity_button_list", {
    ...listView,
    Controller: OpportunityDropdownListController,
    buttonTemplate: "OpportunityDropdownButton",
});

registry.category("ir.actions.report handlers").add("xlsx", async (action) => {
    if (action.report_type === 'xlsx') {
        BlockUI;
        await download({
            url: '/xlsx_reports',
            data: action.data,
            complete: () => BlockUI.unblock(),   // desbloquea UI al acabar
            error: (error) => action.env.services.crash_manager.rpc_error(error),
        });
        return true;
    }
});

