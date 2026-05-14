/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class HrDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.ui = useService("ui");
        this.state = useState({
            kpi: { employees: 0, jobs: 0, jobs_pub: 0 },
            recent: JSON.parse(sessionStorage.getItem("hr_recent") || "[]"),
            q: "",
            loading: true,
            canPublish: false,
        });
        this.loadAll();
        onMounted(() => this.bindHotkeys());
    }
    async loadAll() {
        const uid = await this.orm.call("res.users", "has_group", [false, "hr.group_hr_manager"]);
        const [emp, jobs, jobsPub] = await Promise.all([
            this.orm.searchCount("hr.employee", []),
            this.orm.searchCount("hr.job", []),
            this.orm.searchCount("hr.job", [["website_published", "=", true]]).catch(() => 0),
        ]);
        this.state.kpi = { employees: emp, jobs, jobs_pub: jobsPub };
        this.state.canPublish = !!uid;
        this.state.loading = false;
    }
    bindHotkeys() {
        const h = (e, k, fn) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === k) { e.preventDefault(); fn(); } };
        window.addEventListener("keydown", e => {
            h(e, "k", () => this.$(".o_hr_search")?.focus());
            if (document.activeElement?.classList.contains("o_hr_search")) return;
            h(e, "e", () => this.openEmployees());
            h(e, "v", () => this.openJobs());
            h(e, "n", () => this.quickCreate());
        });
    }
    async openEmployees(domain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Empleados",
            res_model: "hr.employee",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain,
        });
    }
    async openJobs(domain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Vacantes",
            res_model: "hr.job",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain,
        });
    }
    quickCreate() {
        const target = this.state.lastCard || "job";
        const model = target === "job" ? "hr.job" : "hr.employee";
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            views: [[false, "form"]],
            target: "current",
            context: { default_website_published: false },
        });
    }
    async togglePublish(jobId, current) {
        if (!this.state.canPublish) return;
        await this.orm.write("hr.job", [jobId], { website_published: !current });
        this.loadAll();
    }
    async search(q) {
        this.state.q = q;
        if (!q || q.length < 2) return [];
        const emp = await this.orm.searchRead("hr.employee", [["name", "ilike", q]], ["name"], { limit: 5 });
        const jobs = await this.orm.searchRead("hr.job", [["name", "ilike", q]], ["name", "website_published"], { limit: 5 });
        return { emp, jobs };
    }
    remember(link) {
        const arr = [{ ...link, ts: Date.now() }, ...this.state.recent].slice(0, 5);
        this.state.recent = arr;
        sessionStorage.setItem("hr_recent", JSON.stringify(arr));
    }
}
HrDashboard.template = "hr_job_vacancies_website.HrDashboardPro";
registry.category("actions").add("hr_vacancies.dashboard_pro", HrDashboard);
