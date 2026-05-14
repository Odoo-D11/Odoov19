/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { Component, useState, onMounted, onWillStart, onWillUnmount, useRef } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { NewRequestWizardDialog } from "@purchase_management/components/new_request_wizard/new_request_wizard";

const COLORS = [
    "#1abc9c", "#2ecc71", "#3498db", "#9b59b6", "#e67e22",
    "#e74c3c", "#f1c40f", "#34495e", "#16a085", "#27ae60",
    "#2980b9", "#8e44ad", "#d35400", "#c0392b", "#f39c12", "#7f8c8d",
];
let colorIndex = 0;
const getColor = () => COLORS[colorIndex++ % COLORS.length];

const TYPE_COLORS = ["#3498db", "#e67e22", "#9b59b6", "#27ae60", "#e74c3c"];

const CATEGORY_CONFIG = [
    {
        key: 'project', label: 'Proyectos', icon: 'fa-briefcase', color: '#2980b9',
        domain: [['category', '=', 'project']]
    },
    {
        key: 'admin', label: 'Administrativo', icon: 'fa-building', color: '#8e44ad',
        domain: [['category', '=', 'admin']]
    },
];

const OVERDUE_ELIGIBLE_STATES = [
    'in_shopping', 'sent',
    'pending_project_approval', 'pending_purchase_approval',
    'pending_advisory_committee_approval',
];

const STATE_CONFIG = [
    {
        key: 'draft', label: 'Borrador', icon: 'fa-file-o', color: '#6c757d',
        domain: [['state', '=', 'draft']]
    },
    {
        key: 'in_shopping', label: 'En Compras', icon: 'fa-shopping-cart', color: '#2c7be5',
        domain: [['state', '=', 'in_shopping']]
    },
    {
        key: 'sent', label: 'Enviadas', icon: 'fa-paper-plane-o', color: '#5bc0de',
        domain: [['state', '=', 'sent']]
    },
    {
        key: 'pending_approval', label: 'Pendientes', icon: 'fa-clock-o', color: '#f39c12',
        domain: [['state', 'in', ['pending_project_approval', 'pending_purchase_approval', 'pending_advisory_committee_approval']]]
    },
    {
        key: 'approved', label: 'Aprobadas', icon: 'fa-check-circle', color: '#27ae60',
        domain: [['state', '=', 'approved']]
    },
    {
        key: 'cancelled', label: 'Canceladas', icon: 'fa-ban', color: '#e74c3c',
        domain: ['|', ['state', '=', 'cancelled'], ['active', '=', false]]
    },
    {
        key: 'overdue', label: 'Vencidas', icon: 'fa-exclamation-triangle', color: '#c0392b',
        domain: []
    },
];

export class PurchaseStatusSidebar extends Component {
    static template = "purchase_management.PurchaseStatusSidebar";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            stateData: Object.fromEntries(STATE_CONFIG.map(s => [s.key, 0])),
            categoryData: Object.fromEntries(CATEGORY_CONFIG.map(c => [c.key, 0])),
            types: [],
            personnel: [],
            loading: true,
            activeSection: null,
            activeId: null,
            personnelHidden: false,
            personnelExpanded: false,
            personnelSearch: '',
            personnelSearchActive: false,
            overdueData: {
                total_active: 0, by_shopping: 0, by_sent: 0,
                by_approval: 0, by_project: 0, by_admin: 0,
                avg_days: 0, max_days: 0,
            },
            overdueSubFilter: null, // { section, key } cuando hay un sub-filtro activo en el panel de vencidas
        });
        this.stateConfig = STATE_CONFIG;
        this.categoryConfig = CATEGORY_CONFIG;
        this.PERSONNEL_LIMIT = 5;
        this.personnelSearchRef = useRef('personnelSearchInput');
        this._nonSidebarDomain = [];
        this._lastDomainKey = '';
        this._searchUpdateTimeout = null;

        // SearchModel emite "update" en cada cambio de filtro. El setTimeout(0) agrupa
        // disparos síncronos consecutivos (como limpiar + crear un filtro) en una sola
        // ejecución, evitando recargas intermedias con estado inconsistente.
        useBus(this.env.searchModel, "update", () => {
            clearTimeout(this._searchUpdateTimeout);
            this._searchUpdateTimeout = setTimeout(() => this._onSearchModelUpdate(), 0);
        });

        onWillStart(async () => {
            try {
                const sm = this.env.searchModel;
                if (sm) {
                    const myAssigned = sm.getSearchItems(f => f.name === 'my_assigned' && f.isActive).length > 0;
                    this.state.personnelHidden = myAssigned;
                    const sidebarActive = sm.getSearchItems(f => f.isFromPurchaseSidebar && f.isActive).length > 0;
                    if (!sidebarActive) {
                        this._nonSidebarDomain = sm.domain || [];
                        this._lastDomainKey = JSON.stringify(this._nonSidebarDomain);
                    }
                    // Al remontar el componente (ej: volver de un formulario), useBus no dispara
                    // porque no hubo cambio de filtro, así que restauramos el panel manualmente.
                    this._restoreActivePanel(sm);
                }
                await this.loadData();
            } catch (error) {
                console.error("Error inicializando RFQ sidebar:", error);
            }
        });

        onWillUnmount(() => {
            clearTimeout(this._searchUpdateTimeout);
        });
    }

    _onSearchModelUpdate() {
        const sm = this.env.searchModel;
        if (!sm) return;

        // Si el usuario quitó el filtro del sidebar desde el buscador, limpiar estado local
        if (this.state.activeSection) {
            if (!sm.getSearchItems(f => f.isFromPurchaseSidebar && f.isActive).length) {
                // Solo limpiar si tampoco hay un filtro nativo que deba mantener la sección abierta
                const namedFilters = ['overdue', 'pending_approval', 'in_shopping', 'sent_to_suppliers', 'closed_requests', 'cancelled'];
                const hasActiveNamed = sm.getSearchItems(f => namedFilters.includes(f.name) && f.isActive).length > 0;
                
                if (!hasActiveNamed) {
                    this.state.activeSection = null;
                    this.state.activeId = null;
                    this.state.overdueSubFilter = null;
                }
            }
        }

        // Fallback: si se activó un filtro nativo (vía search_default o búsqueda manual), 
        // resaltar automáticamente la sección correspondiente del sidebar.
        const namedFiltersMap = {
            'overdue':           { section: 'state', id: 'overdue' },
            'pending_approval':  { section: 'state', id: 'pending_approval' },
            'in_shopping':       { section: 'state', id: 'in_shopping' },
            'sent_to_suppliers': { section: 'state', id: 'sent' },
            'closed_requests':   { section: 'state', id: 'approved' },
            'cancelled':         { section: 'state', id: 'cancelled' },
        };

        for (const [name, target] of Object.entries(namedFiltersMap)) {
            if (sm.getSearchItems(f => f.name === name && f.isActive).length > 0) {
                if (this.state.activeSection !== target.section || this.state.activeId !== target.id) {
                    this.state.activeSection = target.section;
                    this.state.activeId = target.id;
                }
                break;
            }
        }

        const sidebarActive = sm.getSearchItems(f => f.isFromPurchaseSidebar && f.isActive).length > 0;
        const myAssigned = sm.getSearchItems(f => f.name === 'my_assigned' && f.isActive).length > 0;

        if (myAssigned !== this.state.personnelHidden) {
            this.state.personnelHidden = myAssigned;
            this.state.personnelExpanded = false;
            this.state.personnelSearch = '';
            this.state.personnelSearchActive = false;
            if (!sidebarActive) {
                this._nonSidebarDomain = sm.domain || [];
                this._lastDomainKey = JSON.stringify(this._nonSidebarDomain);
            }
            this.loadData(true);
            return;
        }

        if (!sidebarActive) {
            const domainKey = JSON.stringify(sm.domain || []);
            if (domainKey !== this._lastDomainKey) {
                this._lastDomainKey = domainKey;
                this._nonSidebarDomain = sm.domain || [];
                this.loadData(true);
            }
        }
    }

    _applyOverdueFilter() {
        const sm = this.env.searchModel;
        this._clearSidebarFilters();

        const today = new Date().toISOString().split('T')[0];
        const sub = this.state.overdueSubFilter;

        let domain = [
            ['deadline', '<', today],
            ['state', 'in', OVERDUE_ELIGIBLE_STATES],
        ];
        let description = 'Vencidas';
        let sidebarSubFilter = null;

        if (sub) {
            sidebarSubFilter = { section: sub.section, key: sub.key };
            if (sub.section === 'state') {
                if (sub.key === 'in_shopping') {
                    domain.push(['state', '=', 'in_shopping']);
                    description = 'Vencidas · En Compras';
                } else if (sub.key === 'sent') {
                    domain.push(['state', '=', 'sent']);
                    description = 'Vencidas · Enviadas';
                } else if (sub.key === 'approval') {
                    domain.push(['state', 'in', [
                        'pending_project_approval',
                        'pending_purchase_approval',
                        'pending_advisory_committee_approval',
                    ]]);
                    description = 'Vencidas · En Aprobación';
                }
            } else if (sub.section === 'category') {
                domain.push(['category', '=', sub.key]);
                description = sub.key === 'project' ? 'Vencidas · Proyectos' : 'Vencidas · Administrativo';
            } else if (sub.section === 'max') {
                const maxDays = this.state.overdueData.max_days || 0;
                const maxDate = new Date();
                maxDate.setDate(maxDate.getDate() - maxDays);
                domain.push(['deadline', '<=', maxDate.toISOString().split('T')[0]]);
                description = 'Vencidas · Mayor atraso';
            }
        }

        sm.createNewFilters([{
            description,
            domain,
            isFromPurchaseSidebar: true,
            sidebarSection: 'state',
            sidebarId: 'overdue',
            sidebarSubFilter,
        }]);

        this.state.activeSection = 'state';
        this.state.activeId = 'overdue';
    }

    _restoreActivePanel(sm) {
        // Recuperar el panel activo desde la metadata del filtro guardado en SearchModel (Custom Filters)
        const sidebarItems = sm.getSearchItems(f => f.isFromPurchaseSidebar && f.isActive);
        if (sidebarItems.length > 0) {
            const item = sidebarItems[0];
            if (item.sidebarSection !== undefined && item.sidebarId !== undefined) {
                this.state.activeSection = item.sidebarSection;
                this.state.activeId = item.sidebarId;
                if (item.sidebarSubFilter) {
                    this.state.overdueSubFilter = item.sidebarSubFilter;
                }
                return;
            }
        }

        // Fallback: si se activó un filtro nativo (vía search_default), mapear a sección del sidebar
        const namedFiltersMap = {
            'overdue':           { section: 'state',    id: 'overdue' },
            'pending_approval':  { section: 'state',    id: 'pending_approval' },
            'in_shopping':       { section: 'state',    id: 'in_shopping' },
            'sent_to_suppliers': { section: 'state',    id: 'sent' },
            'closed_requests':   { section: 'state',    id: 'approved' },
            'cancelled':         { section: 'state',    id: 'cancelled' },
        };

        for (const [name, target] of Object.entries(namedFiltersMap)) {
            if (sm.getSearchItems(f => f.name === name && f.isActive).length > 0) {
                this.state.activeSection = target.section;
                this.state.activeId = target.id;
                return;
            }
        }
    }

    filterOverdueSub(section, key) {
        const isSame = this.state.overdueSubFilter?.section === section
                    && this.state.overdueSubFilter?.key === key;
        this.state.overdueSubFilter = isSame ? null : { section, key };
        this._applyOverdueFilter();
    }

    isOverdueSubActive(section, key) {
        return this.state.overdueSubFilter?.section === section
            && this.state.overdueSubFilter?.key === key;
    }

    async loadData(silent = false) {
        if (!silent) {
            this.state.loading = true;
        }
        try {
            const result = await this.orm.call(
                "request.quotation", "retrieve_sidebar_data",
                [this.state.personnelHidden, this._nonSidebarDomain || []]
            );
            this.state.stateData = result.states;
            this.state.categoryData = result.categories || this.state.categoryData;
            this.state.types = (result.types || []).map((t, i) => ({
                ...t, color: TYPE_COLORS[i % TYPE_COLORS.length],
            }));
            colorIndex = 0;
            this.state.personnel = result.personnel.map(p => ({ ...p, color: getColor() }));
            this.state.overdueData = result.overdue_summary || this.state.overdueData;
        } catch (e) {
            console.error("Error cargando sidebar:", e);
        }
        this.state.loading = false;
    }

    get filteredPersonnel() {
        let list = this.state.personnel;
        if (this.state.personnelSearch) {
            const q = this.state.personnelSearch.toLowerCase();
            list = list.filter(p => p.name.toLowerCase().includes(q));
        } else if (!this.state.personnelExpanded) {
            list = list.slice(0, this.PERSONNEL_LIMIT);
        }
        return list;
    }

    togglePersonnelSearch() {
        this.state.personnelSearchActive = !this.state.personnelSearchActive;
        if (!this.state.personnelSearchActive) {
            this.state.personnelSearch = '';
        } else {
            Promise.resolve().then(() => this.personnelSearchRef.el?.focus());
        }
    }

    togglePersonnelExpanded() {
        this.state.personnelExpanded = !this.state.personnelExpanded;
    }

    onPersonnelSearchInput(ev) {
        this.state.personnelSearch = ev.target.value;
    }

    filterByCategory(cfg) {
        const sm = this.env.searchModel;
        if (!sm) return;

        this._clearSidebarFilters();

        if (this.state.activeSection === 'category' && this.state.activeId === cfg.key) {
            this.state.activeSection = null;
            this.state.activeId = null;
            return;
        }

        sm.createNewFilters([{
            description: cfg.label,
            domain: cfg.domain,
            isFromPurchaseSidebar: true,
            sidebarSection: 'category',
            sidebarId: cfg.key,
        }]);

        this.state.activeSection = 'category';
        this.state.activeId = cfg.key;
    }

    filterByType(item) {
        const sm = this.env.searchModel;
        if (!sm) return;

        this._clearSidebarFilters();

        if (this.state.activeSection === 'type' && this.state.activeId === item.id) {
            this.state.activeSection = null;
            this.state.activeId = null;
            return;
        }

        sm.createNewFilters([{
            description: item.name,
            domain: [['type_id', '=', item.id]],
            isFromPurchaseSidebar: true,
            sidebarSection: 'type',
            sidebarId: item.id,
        }]);

        this.state.activeSection = 'type';
        this.state.activeId = item.id;
    }

    filterByState(cfg) {
        const sm = this.env.searchModel;
        if (!sm) return;

        this._clearSidebarFilters();

        if (this.state.activeSection === 'state' && this.state.activeId === cfg.key) {
            this.state.activeSection = null;
            this.state.activeId = null;
            this.state.overdueSubFilter = null;
            // Si el panel de vencidas fue abierto desde el buscador, apagar ese filtro también
            if (cfg.key === 'overdue') {
                sm.getSearchItems(f => f.name === 'overdue' && f.isActive && !f.isFromPurchaseSidebar)
                    .forEach(f => sm.toggleSearchItem(f.id));
            }
            return;
        }

        if (cfg.key === 'overdue') {
            this.state.overdueSubFilter = null;
            this._applyOverdueFilter();
            return;
        }

        sm.createNewFilters([{
            description: cfg.label,
            domain: cfg.domain,
            isFromPurchaseSidebar: true,
            sidebarSection: 'state',
            sidebarId: cfg.key,
        }]);

        this.state.activeSection = 'state';
        this.state.activeId = cfg.key;
    }

    filterByPersonnel(item) {
        const sm = this.env.searchModel;
        if (!sm) return;

        this._clearSidebarFilters();

        if (this.state.activeSection === 'personnel' && this.state.activeId === item.id) {
            this.state.activeSection = null;
            this.state.activeId = null;
            return;
        }

        sm.createNewFilters([{
            description: item.name,
            domain: ['|', ['responsible_id', '=', item.id],
                ['responsible_purchase_id.employee_id', '=', item.id]],
            isFromPurchaseSidebar: true,
            sidebarSection: 'personnel',
            sidebarId: item.id,
        }]);

        this.state.activeSection = 'personnel';
        this.state.activeId = item.id;
    }

    _clearSidebarFilters() {
        const sm = this.env.searchModel;
        if (!sm) return;
        sm.getSearchItems(f => f.isFromPurchaseSidebar)
            .filter(f => f.isActive)
            .forEach(f => sm.toggleSearchItem(f.id));
    }

    isItemActive(section, id) {
        return this.state.activeSection === section && this.state.activeId === id;
    }

    // Colapsado cuando "Mis solicitudes" está activo o no hay empleados con solicitudes
    get isPersonnelCollapsed() {
        return this.state.personnelHidden || this.state.personnel.length === 0;
    }

    get visibleTypes() {
        return this.state.types.filter(t => t.count > 0);
    }

    get visibleCategoryConfig() {
        return this.categoryConfig.filter(cfg => (this.state.categoryData[cfg.key] || 0) > 0);
    }

    get visibleStateConfig() {
        return this.stateConfig.filter(cfg => (this.state.stateData[cfg.key] || 0) > 0);
    }

    get isOverdueActive() {
        return this.state.activeSection === 'state' && this.state.activeId === 'overdue';
    }

    get hasNoData() {
        return this.state.personnelHidden
            && this.visibleTypes.length === 0
            && this.visibleCategoryConfig.length === 0
            && this.visibleStateConfig.length === 0;
    }
}

/**
 * Inyecta filtros dinámicos temporales (facets) desde el contexto de la acción.
 * Limpia filtros previos para asegurar coherencia con los datos del Dashboard.
 */
function useDynamicFacets(component) {
    const facets = component.props.context?.dynamic_search_facets;
    if (facets && Array.isArray(facets) && facets.length > 0) {
        onMounted(() => {
            const sm = component.env.searchModel;
            if (!sm?.createNewFilters) return;
            // Inyectamos las facetas dinámicas (chips removibles en la barra de búsqueda).
            sm.createNewFilters(facets);
        });
    }
}

export class PurchaseManagementListController extends ListController {
    setup() {
        super.setup();
        this.action = useService("action");
        this.dialogService = useService("dialog");
        this.state = useState({
            ...this.state,
            isCreatorGroup: false,
        });

        // Aplicar lógica de filtros dinámicos
        useDynamicFacets(this);

        onWillStart(async () => {
            this.state.isCreatorGroup = await user.hasGroup(
                "purchase_management.group_project_leader_purchase_management"
            ) || await user.hasGroup("purchase_management.group_process_leader_purchase_management");
        });
    }

    async createRecord() {
        /* Comentado para abrir directamente la vista form de request.quotation
        if (!this.state.isCreatorGroup) {
            return super.createRecord();
        }
        this.dialogService.add(NewRequestWizardDialog, {
            onConfirm: async (id) => {
                await this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "request.quotation",
                    res_id: id,
                    views: [[false, "form"]],
                    target: "current",
                });
            },
        });
        */
        return super.createRecord();
    }

}

PurchaseManagementListController.template = "purchase_management.PurchaseManagementListView";
PurchaseManagementListController.components = {
    ...ListController.components,
    PurchaseStatusSidebar,
};

export const purchaseManagementListBannerView = {
    ...listView,
    Controller: PurchaseManagementListController,
    buttonTemplate: "purchase_management.PurchaseManagementDropdownButton",
};

registry.category("views").add("rfq_list_sidebar", purchaseManagementListBannerView);

/**
 * Controlador para la vista lista de Órdenes de Compra.
 * Permite la inyección de filtros dinámicos temporales sin persistencia.
 */
export class PurchaseOrderListController extends ListController {
    setup() {
        super.setup();
        useDynamicFacets(this);
    }
}

export const purchaseOrderListView = {
    ...listView,
    Controller: PurchaseOrderListController,
};

registry.category("views").add("purchase_order_list_view", purchaseOrderListView);
