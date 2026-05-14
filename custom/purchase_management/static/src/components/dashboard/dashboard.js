/** @odoo-module **/

import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { user } from "@web/core/user";

const ACTION_TAG = "purchase_management_dashboard";


const QUOTES = [
    { text: "La calidad nunca es un accidente; siempre es el resultado de un esfuerzo inteligente, una atención genuina y una ejecución hábil.", author: "John Ruskin" },
    { text: "Lo que se mide se gestiona, y lo que se gestiona puede mejorarse continuamente hasta alcanzar niveles de excelencia sostenible.", author: "Peter Drucker" },
    { text: "La eficiencia consiste en hacer bien las cosas. La efectividad consiste en hacer las cosas correctas en el momento correcto.", author: "Peter Drucker" },
    { text: "El éxito no es definitivo, el fracaso no es fatal: lo que cuenta es el coraje de continuar avanzando con determinación.", author: "Winston Churchill" },
    { text: "La mejor preparación para el mañana es hacer el trabajo de hoy con excelencia, precisión y total compromiso.", author: "William Osler" },
    { text: "Un equipo alineado alrededor de una visión clara puede transformar los desafíos más complejos en oportunidades extraordinarias.", author: "Bill Walsh" },
    { text: "La planificación a largo plazo no consiste en pensar en decisiones futuras, sino en pensar en el futuro de las decisiones presentes.", author: "Peter Drucker" },
    { text: "La disciplina es el puente que une las metas y los logros. Sin ella, la visión más brillante permanece como simple fantasía.", author: "Jim Rohn" },
];

// Colors for supplier avatars / treemap cells
const AVATAR_COLORS = ["#4361ee", "#2a9d8f", "#e63946", "#f4a261", "#457b9d", "#e9c46a"];

function treemapLayout(items, x, y, w, h) {
    if (!items.length) return [];
    if (items.length === 1) return [{ ...items[0], x, y, w, h }];
    const total = items.reduce((s, i) => s + i.value, 0);
    let sum = 0, split = 1;
    const half = total / 2;
    for (let i = 0; i < items.length - 1; i++) {
        sum += items[i].value;
        split = i + 1;
        if (sum >= half) break;
    }
    const leftRatio = items.slice(0, split).reduce((s, i) => s + i.value, 0) / total;
    if (w >= h) {
        const lw = w * leftRatio;
        return [
            ...treemapLayout(items.slice(0, split), x, y, lw, h),
            ...treemapLayout(items.slice(split), x + lw, y, w - lw, h),
        ];
    }
    const lh = h * leftRatio;
    return [
        ...treemapLayout(items.slice(0, split), x, y, w, lh),
        ...treemapLayout(items.slice(split), x, y + lh, w, h - lh),
    ];
}

export class PurchaseManagementDashboard extends Component {
    static template = "purchase_management.PurchaseManagementDashboard";

    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");
        this.quote  = QUOTES[Math.floor(Math.random() * QUOTES.length)];

        // Chart canvas refs
        this.trendRef    = useRef("trendChart");
        this.donutRef    = useRef("donutChart");
        this.convRef     = useRef("convSparkline");
        this.daysRef     = useRef("daysSparkline");
        this.ocValRef    = useRef("ocValSparkline");
        this.trmUsdRef   = useRef("trmUsdChart");
        this.trmEurRef   = useRef("trmEurChart");
        this.activityRef = useRef("activityChart");

        // Chart instances (for cleanup)
        this._charts = [];

        this.state = useState({
            loading: true,
            kpis: {
                sdc_total: 0, sdc_this_month: 0, sdc_prev_month: 0,
                sdc_in_process: 0, sdc_overdue: 0, sdc_pending: 0,
                oc_total: 0, oc_total_value: 0, oc_sent: 0, oc_caused: 0, oc_paid: 0,
                sdc_unassigned: 0, sdc_category_project: 0, sdc_category_admin: 0,
                sagrilaft_alert_count: 0, oc_prev_month_value: 0,
                oc_foreign_count: 0, oc_foreign_value_cop: 0,
            },
            charts: null,
            trm: {},
            currencies: {},
            recent_sdc: [],
            sdc_monthly: [],
            oc_monthly: [],
            sdc_deadline_map: {},
            calendarYear: new Date().getFullYear(),
            calendarMonth: new Date().getMonth(),
            selectedCalDay: null,
            sdcSearch: "",
            sdcSearchResults: null,
            sdcSearchLoading: false,
            sdcStateFilter: 'all',
            sdc_approved_count: 0,
            // Filtro por integrante del equipo
            teamMembers: [],
            filterMemberId: false,
            teamDropdownOpen: false,
            teamSearch: "",
        });

        onWillStart(async () => {
            // Paso 1: team members + Chart.js en paralelo
            const [teamData] = await Promise.all([
                this.orm.call("request.quotation", "get_purchase_team_members", [], {}),
                loadJS("/web/static/lib/Chart/Chart.js"),
            ]);
            this.state.teamMembers = teamData.members || [];
            
            // Intentar recuperar integrante persistido en la sesión
            const persistedId = sessionStorage.getItem("pm_dashboard_member_id");
            if (persistedId) {
                this.state.filterMemberId = parseInt(persistedId);
            } else {
                this.state.filterMemberId = teamData.current_member_id || false;
            }

            // Mostrar nombre del usuario activo en el input desde el inicio
            const initMember = this.state.teamMembers.find(x => x.id === this.state.filterMemberId);
            this.state.teamSearch = initMember ? initMember.name : "";

            // Paso 2: cargar dashboard con el filtro del usuario activo
            await this._fetchDashboardData();
            this.state.loading = false;
        });

        onMounted(() => {
            if (!this.state.loading) this._renderAllCharts();
            this._closeTeamDropdown = () => { this.state.teamDropdownOpen = false; };
            document.addEventListener("click", this._closeTeamDropdown);
        });

        onPatched(() => {
            // Re-renderizar charts después de reload de datos (DOM intacto, refs válidos)
            if (this._needsChartRender) {
                this._needsChartRender = false;
                this._renderAllCharts();
            }
        });

        onWillUnmount(() => {
            this._charts.forEach(c => { try { c.destroy(); } catch (_) {} });
            this._charts = [];
            document.removeEventListener("click", this._closeTeamDropdown);
        });
    }

    // ─── Team filter ──────────────────────────────────────────────────────────

    toggleTeamDropdown = (ev) => {
        ev.stopPropagation();
        this.state.teamDropdownOpen = !this.state.teamDropdownOpen;
        if (this.state.teamDropdownOpen) this.state.teamSearch = "";
    }

    openTeamDropdown = (ev) => {
        ev.stopPropagation();
        this.state.teamDropdownOpen = true;
    }

    onTeamInput = (ev) => {
        ev.stopPropagation();
        this.state.teamSearch = ev.target.value;
        this.state.teamDropdownOpen = true;
    }

    get filteredTeamMembers() {
        const q = (this.state.teamSearch || "").toLowerCase();
        if (!q) return this.state.teamMembers;
        return this.state.teamMembers.filter(m => m.name.toLowerCase().includes(q));
    }

    selectTeamMember = async (ev, memberId) => {
        ev && ev.stopPropagation && ev.stopPropagation();
        if (this.state.filterMemberId === memberId) {
            this.state.teamDropdownOpen = false;
            return;
        }
        this.state.filterMemberId = memberId;
        this.state.teamDropdownOpen = false;

        // Persistir selección en la sesión del navegador
        if (memberId) {
            sessionStorage.setItem("pm_dashboard_member_id", memberId);
        } else {
            sessionStorage.removeItem("pm_dashboard_member_id");
        }

        // Mostrar nombre seleccionado en el input, o vaciar si se limpia
        const selected = this.state.teamMembers.find(x => x.id === memberId);
        this.state.teamSearch = selected ? selected.name : "";
        
        // Destruir charts previos para evitar superposición
        this._charts.forEach(c => { try { c.destroy(); } catch (_) {} });
        this._charts = [];
        
        await this._fetchDashboardData();
        // Marcar para renderizar charts en el siguiente onPatched
        this._needsChartRender = true;
    }

    async _fetchDashboardData() {
        const memberId = this.state.filterMemberId || false;
        const [data, charts, trends, trm] = await Promise.all([
            this.orm.call("request.quotation", "get_dashboard_data",        [], { member_id: memberId }),
            this.orm.call("request.quotation", "get_dashboard_charts_data", [], { member_id: memberId }),
            this.orm.call("request.quotation", "get_dashboard_trends",      [], { member_id: memberId }),
            this.orm.call("request.quotation", "get_trm_history",           [], {}),
        ]);
        this.state.currencies        = data.currencies || {};
        this.state.trm               = trm || {};
        this.state.recent_sdc        = data.recent_sdc || [];
        this.state.sdc_monthly       = trends.sdc_monthly || [];
        this.state.oc_monthly        = trends.oc_monthly  || [];
        this.state.sdc_deadline_map  = data.sdc_deadline_map || {};
        this.state.charts            = charts || {};
        this.state.sdc_approved_count = data.sdc_approved_count || 0;
        const oc = data.oc || {};
        this.state.kpis = {
            sdc_total:            data.sdc?.total         || 0,
            sdc_this_month:       data.sdc_this_month     || 0,
            sdc_prev_month:       data.sdc_prev_month     || 0,
            sdc_in_process:       data.sdc?.in_process    || 0,
            sdc_overdue:          data.sdc?.overdue       || 0,
            sdc_pending:          data.sdc?.pending       || 0,
            oc_total:             oc.total   || 0,
            oc_total_value:       data.oc_total_value     || 0,
            oc_sent:              oc.sent    || 0,
            oc_caused:            oc.caused  || 0,
            oc_paid:              oc.paid    || 0,
            sdc_unassigned:       data.sdc_unassigned     || 0,
            sdc_category_project: data.sdc_category_project || 0,
            sdc_category_admin:   data.sdc_category_admin   || 0,
            oc_prev_month_value:  data.oc_prev_month_value || 0,
            oc_foreign_count:     data.oc_foreign_count   || 0,
            oc_foreign_value_cop: data.oc_foreign_value_cop || 0,
            sdc_management:       data.sdc?.management_total || 0,
        };
    }

    get activeFilterLabel() {
        if (!this.state.filterMemberId) return null;
        const m = this.state.teamMembers.find(x => x.id === this.state.filterMemberId);
        return m ? m.name.split(" ")[0] : null;
    }

    // ─── Getters — header ──────────────────────────────────────────────────────

    get userName() { return (user.name || "").split(" ")[0]; }
    get todayDayNumber() { return new Date().getDate(); }
    get todayMonthLabel() {
        const d = new Date();
        const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                        "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
        return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
    }
    get formattedDate() {
        const raw = new Date().toLocaleDateString("es-CO", {
            weekday: "long", year: "numeric", month: "long", day: "numeric",
        });
        return raw.charAt(0).toUpperCase() + raw.slice(1);
    }

    // ─── Getters — Section 1 ──────────────────────────────────────────────────

    get overduePercent() {
        const t = this.state.kpis.sdc_total;
        return t ? Math.round((this.state.kpis.sdc_overdue / t) * 100) : 0;
    }
    get labelOverdue()   { return this.state.kpis.sdc_overdue    === 1 ? "Solicitud Vencida"    : "Solicitudes Vencidas"; }
    get labelPending()   { return this.state.kpis.sdc_pending    === 1 ? "Solicitud Pendiente"  : "Solicitudes Pendientes"; }
    get labelInProcess() { return this.state.kpis.sdc_in_process === 1 ? "Solicitud en Gestión" : "Solicitudes en Gestión"; }
    get labelTotal()     { return this.state.kpis.sdc_total      === 1 ? "Solicitud Total"      : "Solicitudes Totales"; }
    get labelOrders()    { return this.state.kpis.oc_total       === 1 ? "Orden de Compra"      : "Órdenes de Compra"; }

    get sdcMonthChange() {
        const cur = this.state.kpis.sdc_this_month;
        const prv = this.state.kpis.sdc_prev_month;
        if (!prv) return { val: cur, pct: null, dir: "neutral" };
        const pct = Math.round(((cur - prv) / prv) * 100);
        return { val: cur, pct: Math.abs(pct), dir: pct >= 0 ? "up" : "down" };
    }

    // ─── Getters — Section 2 ─────────────────────────────────────────────────

    get stateDistWithPct() {
        const ICONS = {
            in_shopping:                          'fa-shopping-cart',
            sent:                                 'fa-paper-plane',
            pending_project_approval:             'fa-user',
            pending_purchase_approval:            'fa-building',
            pending_advisory_committee_approval:  'fa-users',
            approved:                             'fa-check',
            order_created:                        'fa-file-text-o',
        };
        const dist = this.state.charts?.state_dist || [];
        const total = dist.reduce((s, i) => s + i.count, 0) || 1;
        return dist.map(i => ({
            ...i,
            pct:  Math.round((i.count / total) * 100),
            icon: ICONS[i.state] || 'fa-circle',
        }));
    }

    get sdc6MonthsTotal() {
        return (this.state.sdc_monthly || []).reduce((s, m) => s + m.count, 0);
    }
    get conversionRate() {
        return this.state.charts?.efficiency?.conversion_rate || 0;
    }
    get sdcTrendChange() {
        const m = this.state.sdc_monthly || [];
        if (m.length < 2) return null;
        const cur = m[m.length - 1].count;
        const prv = m[m.length - 2].count;
        if (!prv) return null;
        const pct = Math.round(((cur - prv) / prv) * 100);
        return { pct: Math.abs(pct), dir: pct >= 0 ? "up" : "down" };
    }

    // ─── Getters — Section 3 (efficiency) ────────────────────────────────────

    get avgDays()       { return this.state.charts?.efficiency?.avg_days || 0; }
    get ocValueMonth()  { return this.state.charts?.efficiency?.oc_value_month || 0; }
    get ocValueMonthChange() {
        const cur = this.ocValueMonth;
        const prv = this.state.charts?.efficiency?.oc_value_prev_month || 0;
        if (!prv) return { pct: null, dir: "neutral" };
        const pct = Math.round(((cur - prv) / prv) * 100);
        return { pct: Math.abs(pct), dir: pct >= 0 ? "up" : "down" };
    }

    // ─── Getters — Section 4 (TRM) ────────────────────────────────────────────

    get trmUsdChange() { return this._calcTrmChange("USD"); }
    get trmEurChange() { return this._calcTrmChange("EUR"); }
    _calcTrmChange(code) {
        const hist = this.state.trm?.[code]?.history || [];
        if (hist.length < 2) return { pct: null, dir: "neutral" };
        const cur = hist[hist.length - 1].value;
        const prv = hist[hist.length - 2].value;
        if (!prv) return { pct: null, dir: "neutral" };
        const pct = Math.round(((cur - prv) / prv) * 100);
        return { pct: Math.abs(pct), dir: pct >= 0 ? "up" : "down" };
    }
    get todayFormatted() {
        return new Date().toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" });
    }

    // ─── Getters — Section 4 (calendar) ─────────────────────────────────────

    get calendarMonthLabel() {
        const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                        "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
        return `${MONTHS[this.state.calendarMonth]} ${this.state.calendarYear}`;
    }

    get calendarDays() {
        const y = this.state.calendarYear;
        const m = this.state.calendarMonth;
        const firstDay = new Date(y, m, 1);
        const lastDay  = new Date(y, m + 1, 0);
        const todayStr = new Date().toISOString().slice(0, 10);
        const RANK = { overdue: 4, critical: 3, urgent: 2, ok: 1 };

        const days = [];
        const startDow = (firstDay.getDay() + 6) % 7; // Lunes = 0
        for (let i = 0; i < startDow; i++) days.push(null);

        for (let d = 1; d <= lastDay.getDate(); d++) {
            const dateStr = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
            const items = this.state.sdc_deadline_map[dateStr] || [];
            const worst = items.reduce(
                (w, it) => (RANK[it.urgency] || 0) > (RANK[w] || 0) ? it.urgency : w,
                "ok"
            );
            days.push({ day: d, dateStr, items, count: items.length,
                        isToday: dateStr === todayStr, urgency: worst });
        }
        while (days.length % 7 !== 0) days.push(null);
        return days;
    }

    get calendarDeadlineCount() {
        const prefix = `${this.state.calendarYear}-${String(this.state.calendarMonth + 1).padStart(2, "0")}-`;
        return Object.keys(this.state.sdc_deadline_map)
            .filter(k => k.startsWith(prefix))
            .reduce((s, k) => s + (this.state.sdc_deadline_map[k]?.length || 0), 0);
    }

    prevCalMonth = () => {
        if (this.state.calendarMonth === 0) { this.state.calendarMonth = 11; this.state.calendarYear--; }
        else { this.state.calendarMonth--; }
    }

    nextCalMonth = () => {
        if (this.state.calendarMonth === 11) { this.state.calendarMonth = 0; this.state.calendarYear++; }
        else { this.state.calendarMonth++; }
    }

    toggleCalDay = (dateStr) => {
        this.state.selectedCalDay = this.state.selectedCalDay === dateStr ? null : dateStr;
    }

    get calSelectedDayItems() {
        return this.state.sdc_deadline_map[this.state.selectedCalDay] || [];
    }

    get calSelectedDayLabel() {
        if (!this.state.selectedCalDay) return "";
        const [y, m, d] = this.state.selectedCalDay.split("-").map(Number);
        const MONTHS = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                        "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"];
        return `${d} de ${MONTHS[m - 1]}`;
    }

    // ─── Getters — Section 5 (rankings) ─────────────────────────────────────

    get maxProjectCount() {
        const p = this.state.charts?.top_projects || [];
        return p.length ? p[0].count : 1;
    }
    get projectTreemap() {
        const projects = this.state.charts?.top_projects || [];
        if (!projects.length) return [];
        const items = projects.map((p, i) => ({
            id: p.id, name: p.name, value: p.count, color: AVATAR_COLORS[i % AVATAR_COLORS.length],
        }));
        return treemapLayout(items, 0, 0, 100, 100);
    }
    cellHasRoom(cell) { return cell.h >= 12 && cell.w >= 10; }
    sdcLabel(n) { return n === 1 ? "1 Solicitud" : `${n} Solicitudes`; }
    navigateToStateSDC = async (state) => {
        const STATE_LABEL = {
            'in_shopping':                         "En Compras",
            'sent':                                "Enviadas a proveedores",
            'pending_project_approval':            "Pend. Líder Proyecto",
            'pending_purchase_approval':           "Pend. Aprobación Compras",
            'pending_advisory_committee_approval': "Pend. Comité Asesor",
            'approved':                            "Aprobadas",
            'order_created':                       "Orden Creada",
        };
        // 'approved' con miembro: admin siempre incluidas → domain único (igual que Comité)
        const m = this.state.filterMemberId
            ? this.state.teamMembers.find(x => x.id === this.state.filterMemberId)
            : null;

        if (state === 'approved' && m) {
            const domain = ["&", ["state", "=", "approved"], "|",
                ["category", "=", "admin"],
                ["responsible_purchase_id", "=", m.id]];
            const navCtx = {
                dynamic_search_facets: [{ description: `Aprobadas: Admin + ${m.name.split(" ")[0]}`, domain, type: "filter" }],
            };
            return this.action.doAction({
                type: "ir.actions.act_window", name: "Solicitudes de Cotización",
                res_model: "request.quotation",
                view_mode: "list,form", views: [[false, "list"], [false, "form"]],
                target: "current",
                context: navCtx,
            });
        }

        // Estados con filtro nativo en el search view → usar search_default_* para el chip de estado.
        // El filtro de miembro va siempre en dynamic_search_facets.
        const NATIVE_DEFAULT = {
            'in_shopping':   'search_default_in_shopping',
            'sent':          'search_default_sent_to_suppliers',
            'approved':      'search_default_closed_requests',
            'order_created': 'search_default_order_created',
        };
        const nativeKey = NATIVE_DEFAULT[state];

        // Facets: estado (solo si no tiene nativo) + miembro
        const stateFilters = nativeKey ? [] : [{
            description: STATE_LABEL[state] || state,
            domain: [["state", "=", state]],
        }];
        const navCtx = this._navContext("request.quotation", stateFilters);
        if (nativeKey) navCtx[nativeKey] = 1;

        this.action.doAction({
            type: "ir.actions.act_window", name: "Solicitudes de Cotización",
            res_model: "request.quotation",
            view_mode: "list,form", views: [[false, "list"], [false, "form"]],
            target: "current",
            context: navCtx,
        });
    }

    navigateToSupplierOC = async (partnerId, partnerName) => {
        const navCtx = this._navContext("purchase.management.order", [{
            description: `Proveedor: ${partnerName}`,
            domain: [["partner_id", "=", partnerId]],
        }]);
        this.action.doAction({
            type: "ir.actions.act_window", name: "Órdenes de Compra",
            res_model: "purchase.management.order",
            view_mode: "list,form", views: [[false, "list"], [false, "form"]],
            target: "current",
            context: navCtx,
        });
    }

    navigateToProjectSDC = async (projId, projName) => {
        const navCtx = this._navContext("request.quotation", [{
            description: `Proyecto: ${projName}`,
            domain: [["project_id", "=", projId]],
        }]);
        this.action.doAction({
            type: "ir.actions.act_window", name: "Solicitudes de Cotización",
            res_model: "request.quotation",
            view_mode: "list,form", views: [[false, "list"], [false, "form"]],
            target: "current",
            context: navCtx,
        });
    }

    // ─── Getters — Section 7 (category) ──────────────────────────────────────

    get categoryTotal() {
        return (this.state.kpis.sdc_category_project || 0) + (this.state.kpis.sdc_category_admin || 0) || 1;
    }
    get projectPct() { return Math.round((this.state.kpis.sdc_category_project / this.categoryTotal) * 100); }
    get adminPct()   { return Math.round((this.state.kpis.sdc_category_admin   / this.categoryTotal) * 100); }

    // ─── Getters — Section 8 (SDC table) ────────────────────────────────────

    get displayedSdc() {
        return this.state.sdcSearchResults !== null
            ? this.state.sdcSearchResults
            : (this.state.recent_sdc || []);
    }

    // ─── Getters — §3 Management panel ──────────────────────────────────────

    get sdcStateOptions() {
        const sdc = this.state.recent_sdc || [];
        const counts = {};
        sdc.forEach(s => { counts[s.state] = (counts[s.state] || 0) + 1; });
        const LABELS = {
            draft:                                'Borrador',
            pending_project_approval:             'Pend. Proyecto',
            pending_purchase_approval:            'Pend. Compras',
            pending_advisory_committee_approval:  'Pend. Comité',
            in_shopping:                          'En Compras',
            sent_to_suppliers:                    'Enviadas',
            approved:                             'Aprobadas',
            order_created:                        'OC Creada',
            cancelled:                            'Cancelada',
        };
        const options = [{ state: 'all', label: 'Todas', count: sdc.length }];
        Object.entries(counts).sort((a, b) => b[1] - a[1]).forEach(([state, count]) => {
            options.push({ state, label: LABELS[state] || state, count });
        });
        return options;
    }

    get sdcFilteredByState() {
        const sdc = this.state.recent_sdc || [];
        const filtered = this.state.sdcStateFilter === 'all'
            ? sdc
            : sdc.filter(s => s.state === this.state.sdcStateFilter);
        return filtered.slice(0, 6);
    }

    get sdcFilterContext() {
        const f = this.state.sdcStateFilter;
        const MAP = {
            pending_project_approval:             { search_default_pending_approval: 1 },
            pending_purchase_approval:            { search_default_pending_approval: 1 },
            pending_advisory_committee_approval:  { search_default_pending_approval: 1 },
            in_shopping:                          { search_default_in_shopping: 1 },
            sent_to_suppliers:                    { search_default_sent_to_suppliers: 1 },
        };
        return MAP[f] || {};
    }

    setSdcFilter = (stateKey) => {
        this.state.sdcStateFilter = stateKey;
    }

    // ─── Navigation helpers — dynamic_search_facets (chips temporales) ───────

    /**
     * Construye un facet de miembro para inyectar en dynamic_search_facets.
     * @param {string} model  'request.quotation' o 'purchase.management.order'
     * @returns {Object|null}
     */
    _memberFacet(model) {
        if (!this.state.filterMemberId) return null;
        const m = this.state.teamMembers.find(x => x.id === this.state.filterMemberId);
        if (!m) return null;
        const field = model === 'purchase.management.order'
            ? 'request_quotation_id.responsible_purchase_id'
            : 'responsible_purchase_id';
        return {
            description: `Responsable: ${m.name.split(" ")[0]}`,
            domain: [[field, "=", this.state.filterMemberId]],
            type: "filter",
        };
    }

    /**
     * Combina filtros de dominio + filtro de miembro en un array de facets.
     * @param {string} model
     * @param {{description:string, domain:Array}[]} filters
     * @returns {{dynamic_search_facets: Object[]}}
     */
    _navContext(model, filters = []) {
        const memberFacet = this._memberFacet(model);
        const all = memberFacet ? [...filters, memberFacet] : [...filters];
        if (!all.length) return {};
        return { dynamic_search_facets: all.map(f => ({ ...f, type: "filter" })) };
    }

    // ─── Navigation ──────────────────────────────────────────────────────────

    navigateToOverdue = async () => {
        const navCtx = this._navContext("request.quotation");
        navCtx.search_default_overdue = 1;
        this.action.doAction({
            type: "ir.actions.act_window", name: "Solicitudes de Cotización",
            res_model: "request.quotation",
            view_mode: "list,form", views: [[false, "list"], [false, "form"]],
            target: "current",
            context: navCtx,
        });
    }

    navigateToList = async (model, searchContext, name) => {
        const navCtx = { ...(searchContext || {}), ...this._navContext(model) };
        this.action.doAction({
            type: "ir.actions.act_window", name, res_model: model,
            view_mode: "list,form", views: [[false, "list"], [false, "form"]],
            target: "current",
            context: navCtx,
        });
    }

    navigateToManagementSDC = async () => {
        const COMMITTEE = 'pending_advisory_committee_approval';
        const m = this.state.filterMemberId
            ? this.state.teamMembers.find(x => x.id === this.state.filterMemberId)
            : null;

        // Si hay filtro de miembro → estado comité AND (admin OR responsable del miembro)
        // Si no → solo estado comité
        const stateDomain = m
            ? ["&", ["state", "=", COMMITTEE], "|", ["category", "=", "admin"], ["responsible_purchase_id", "=", m.id]]
            : [["state", "=", COMMITTEE]];

        const description = m
            ? `Comité: Admin + ${m.name.split(" ")[0]}`
            : "Pendientes de Comité";

        // No usamos _navContext para el miembro aquí porque ya está embebido en el domain
        const navCtx = {
            dynamic_search_facets: [{ description, domain: stateDomain, type: "filter" }],
        };

        this.action.doAction({
            type: "ir.actions.act_window", name: "Solicitudes de Cotización",
            res_model: "request.quotation",
            view_mode: "list,form", views: [[false, "list"], [false, "form"]],
            target: "current",
            context: navCtx,
        });
    }

    navigateToForm = (model, id) => {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: model,
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    _sdcSearchTimer = null;
    onSDCSearch = (ev) => {
        const q = ev.target.value.trim();
        this.state.sdcSearch = q;
        clearTimeout(this._sdcSearchTimer);
        if (!q) { this.state.sdcSearchResults = null; return; }
        this._sdcSearchTimer = setTimeout(async () => {
            this.state.sdcSearchLoading = true;
            const results = await this.orm.call("request.quotation", "search_sdc_for_dashboard", [q], {});
            this.state.sdcSearchResults = results;
            this.state.sdcSearchLoading = false;
        }, 400);
    }

    formatCurrency(n) {
        return new Intl.NumberFormat("es-CO", {
            style: "currency", currency: "COP", maximumFractionDigits: 0,
        }).format(n || 0);
    }
    formatNumber(n) {
        return new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(n || 0);
    }
    formatCompact(n) {
        if (!n) return "$0";
        if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
        if (n >= 1_000_000)     return `$${(n / 1_000_000).toFixed(1)}M`;
        if (n >= 1_000)         return `$${(n / 1_000).toFixed(0)}K`;
        return `$${Math.round(n)}`;
    }
    avatarColor(index) { return AVATAR_COLORS[index % AVATAR_COLORS.length]; }
    supplierInitials(name) {
        if (!name) return "?";
        const parts = name.trim().split(/\s+/);
        return parts.length >= 2
            ? (parts[0][0] + parts[1][0]).toUpperCase()
            : name.slice(0, 2).toUpperCase();
    }
    deadlineDeltaLabel(days_left) {
        if (days_left === null || days_left === undefined) return "";
        if (days_left < 0) return `hace ${Math.abs(days_left)}d`;
        if (days_left === 0) return "hoy";
        return `en ${days_left}d`;
    }
    formatCOP(val) {
        if (!val) return "$ 0";
        if (val >= 1e9) return `$ ${(val / 1e9).toFixed(1)}B`;
        if (val >= 1e6) return `$ ${(val / 1e6).toFixed(1)}M`;
        if (val >= 1e3) return `$ ${(val / 1e3).toFixed(0)}K`;
        return `$ ${Math.round(val).toLocaleString("es-CO")}`;
    }
    // ─── Chart rendering ─────────────────────────────────────────────────────

    _renderAllCharts() {
        this._renderTrendChart();
        this._renderDonutChart();
        this._renderSparklines();
        this._renderTrmCharts();
        this._renderActivityChart();
    }

    _mkChart(ref, config) {
        const el = ref.el;
        if (!el) return;
        const ctx = el.getContext("2d");
        const chart = new Chart(ctx, config); // eslint-disable-line no-undef
        this._charts.push(chart);
        return chart;
    }

    _renderTrendChart() {
        const sdc = this.state.sdc_monthly || [];
        const oc  = this.state.oc_monthly  || [];
        const labels = sdc.map(m => m.month);
        this._mkChart(this.trendRef, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "SDC",
                        data: sdc.map(m => m.count),
                        borderColor: "#4361ee",
                        backgroundColor: "rgba(67,97,238,0.12)",
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointRadius: 3,
                        pointBackgroundColor: "#4361ee",
                    },
                    {
                        label: "OC",
                        data: oc.map(m => m.count),
                        borderColor: "#2a9d8f",
                        backgroundColor: "rgba(42,157,143,0.10)",
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointRadius: 3,
                        pointBackgroundColor: "#2a9d8f",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { mode: "index", intersect: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 }, color: "#adb5bd" } },
                    y: { grid: { color: "#f1f3f5" }, ticks: { font: { size: 10 }, color: "#adb5bd", precision: 0 }, beginAtZero: true },
                },
            },
        });
    }

    _renderDonutChart() {
        const dist = this.state.charts?.state_dist || [];
        if (!dist.length) return;
        this._mkChart(this.donutRef, {
            type: "doughnut",
            data: {
                labels: dist.map(d => d.label),
                datasets: [{
                    data: dist.map(d => d.count),
                    backgroundColor: dist.map(d => d.color),
                    borderWidth: 0,
                    hoverOffset: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "75%",
                plugins: { 
                    legend: { display: false }, 
                    tooltip: { 
                        backgroundColor: "#212529",
                        padding: 10,
                        bodyFont: { size: 12 },
                        callbacks: {
                            label: ctx => ` ${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed / (this.state.kpis.sdc_in_process || 1) * 100)}%)`,
                        }
                    } 
                },
            },
        });
    }

    _renderSparklines() {
        // Conversión sparkline — línea naranja con tasa de conversión por mes
        const sdc = this.state.sdc_monthly || [];
        const oc  = this.state.oc_monthly  || [];
        const convData = sdc.map((m, i) => m.count ? Math.round(((oc[i]?.count || 0) / m.count) * 100) : 0);
        this._mkChart(this.convRef, this._sparkLineConfig(convData, "#457b9d"));

        // Días promedio sparkline — línea plana con valor de avg_days
        const avgD = this.avgDays;
        const daysData = sdc.map(() => avgD);
        this._mkChart(this.daysRef, this._sparkLineConfig(daysData, "#f4a261"));

        // Valor OC del mes sparkline — línea de valores mensuales OC
        const ocVals = oc.map(m => m.total || 0);
        this._mkChart(this.ocValRef, this._sparkLineConfig(ocVals, "#2a9d8f"));
    }

    _sparkBarConfig(data, color) {
        return {
            type: "bar",
            data: {
                labels: data.map((_, i) => i),
                datasets: [{ data, backgroundColor: color + "99", borderRadius: 2, barPercentage: 0.7 }],
            },
            options: { ...this._sparklineOptions() },
        };
    }
    _sparkLineConfig(data, color) {
        return {
            type: "line",
            data: {
                labels: data.map((_, i) => i),
                datasets: [{
                    data,
                    borderColor: color,
                    backgroundColor: color + "22",
                    fill: true,
                    tension: 0.4,
                    borderWidth: 1.5,
                    pointRadius: 0,
                }],
            },
            options: { ...this._sparklineOptions() },
        };
    }
    _sparklineOptions() {
        return {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
            animation: { duration: 600 },
        };
    }

    _renderTrmCharts() {
        const usd = this.state.trm?.USD?.history || [];
        const eur = this.state.trm?.EUR?.history || [];
        if (usd.length) {
            this._mkChart(this.trmUsdRef, this._sparkLineConfig(usd.map(h => h.value), "#4361ee"));
        }
        if (eur.length) {
            this._mkChart(this.trmEurRef, this._sparkLineConfig(eur.map(h => h.value), "#2a9d8f"));
        }
    }

    _renderActivityChart() {
        const sdc = this.state.sdc_monthly || [];
        const oc  = this.state.oc_monthly  || [];
        const labels = sdc.map(m => m.month);
        this._mkChart(this.activityRef, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "SDC creadas",
                        data: sdc.map(m => m.count),
                        borderColor: "#4361ee",
                        backgroundColor: "rgba(67,97,238,0.08)",
                        fill: true, tension: 0.4, borderWidth: 2.5,
                        pointRadius: 4, pointBackgroundColor: "#4361ee",
                    },
                    {
                        label: "OC generadas",
                        data: oc.map(m => m.count),
                        borderColor: "#2a9d8f",
                        backgroundColor: "rgba(42,157,143,0.08)",
                        fill: true, tension: 0.4, borderWidth: 2.5,
                        pointRadius: 4, pointBackgroundColor: "#2a9d8f",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: true, position: "top",
                        labels: { font: { size: 11 }, color: "#6c757d", boxWidth: 12, padding: 16 } },
                    tooltip: { mode: "index", intersect: false },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 11 }, color: "#adb5bd" } },
                    y: { grid: { color: "#f1f3f5" }, ticks: { font: { size: 11 }, color: "#adb5bd", precision: 0 }, beginAtZero: true },
                },
            },
        });
    }
}

registry.category("actions").add(ACTION_TAG, PurchaseManagementDashboard);
