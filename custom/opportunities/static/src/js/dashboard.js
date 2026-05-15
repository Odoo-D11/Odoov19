/** @odoo-module */

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";

const CHART_JS_CDN = "https://cdn.jsdelivr.net/npm/chart.js";

export class Dashboard extends Component {
    static template = "OpportunitiesDashboardTemplate";

    setup() {
        this.state = useState({
            kpis: [
                {
                    id: "spend",
                    label: "Monto Comprado",
                    value: "$248K",
                    trend: "+12%",
                    trend_color: "success",
                    subtitle: "vs. mes anterior",
                },
                {
                    id: "savings",
                    label: "Ahorros Capturados",
                    value: "$32K",
                    trend: "+4.5%",
                    trend_color: "primary",
                    subtitle: "Negociaciones destacadas",
                },
                {
                    id: "rfq_cycle",
                    label: "Ciclo Promedio RFQ",
                    value: "6.8 días",
                    trend: "-1.2 días",
                    trend_color: "info",
                    subtitle: "Objetivo &lt; 8 días",
                },
                {
                    id: "on_time",
                    label: "Entregas a Tiempo",
                    value: "92%",
                    trend: "+3%",
                    trend_color: "success",
                    subtitle: "Últimos 30 días",
                },
            ],
            quotes: [
                {
                    id: 1,
                    vendor: "Global Supplies",
                    product: "Servidores Rack 2U",
                    amount: "$18,450",
                    status: "Por validar",
                    status_color: "warning",
                },
                {
                    id: 2,
                    vendor: "Logística MX",
                    product: "Transporte terrestre",
                    amount: "$7,980",
                    status: "Confirmada",
                    status_color: "success",
                },
                {
                    id: 3,
                    vendor: "Industrias Verdes",
                    product: "Material reciclado",
                    amount: "$12,300",
                    status: "En negociación",
                    status_color: "info",
                },
            ],
            rfqs: [
                {
                    id: 1,
                    reference: "RFQ/2024/0589",
                    owner: "Laura Martínez",
                    deadline: "15 Abr 2024",
                    priority: "Alta",
                    priority_color: "danger",
                },
                {
                    id: 2,
                    reference: "RFQ/2024/0594",
                    owner: "Carlos Rivera",
                    deadline: "18 Abr 2024",
                    priority: "Media",
                    priority_color: "warning",
                },
                {
                    id: 3,
                    reference: "RFQ/2024/0601",
                    owner: "Ana Gómez",
                    deadline: "22 Abr 2024",
                    priority: "Baja",
                    priority_color: "secondary",
                },
            ],
        });

        this._charts = [];

        onMounted(() => this._initializeCharts());
        onWillUnmount(() => this._disposeCharts());
    }

    async _initializeCharts() {
        if (!window.Chart) {
            await loadJS(CHART_JS_CDN);
        }

        const monthlySpendCtx = this.el.querySelector("#monthlySpendChart");
        const categorySplitCtx = this.el.querySelector("#categorySplitChart");
        const leadTimeCtx = this.el.querySelector("#leadTimeChart");

        if (!monthlySpendCtx || !categorySplitCtx || !leadTimeCtx) {
            return;
        }

        this._charts.push(
            new window.Chart(monthlySpendCtx, {
                type: "line",
                data: {
                    labels: ["Oct", "Nov", "Dic", "Ene", "Feb", "Mar"],
                    datasets: [
                        {
                            label: "Compras",
                            data: [32, 28, 35, 40, 44, 48],
                            borderColor: "#0d6efd",
                            backgroundColor: "rgba(13, 110, 253, 0.1)",
                            borderWidth: 3,
                            tension: 0.4,
                            fill: true,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            mode: "index",
                            intersect: false,
                        },
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { callback: (value) => `${value}K` },
                        },
                    },
                },
            })
        );

        this._charts.push(
            new window.Chart(categorySplitCtx, {
                type: "doughnut",
                data: {
                    labels: ["Tecnología", "Servicios", "Logística", "Suministros"],
                    datasets: [
                        {
                            data: [35, 25, 20, 20],
                            backgroundColor: ["#20c997", "#ffc107", "#fd7e14", "#6f42c1"],
                            borderWidth: 0,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: "bottom",
                            labels: {
                                boxWidth: 12,
                            },
                        },
                    },
                },
            })
        );

        this._charts.push(
            new window.Chart(leadTimeCtx, {
                type: "bar",
                data: {
                    labels: ["Proveedor A", "Proveedor B", "Proveedor C", "Proveedor D"],
                    datasets: [
                        {
                            label: "Días promedio",
                            data: [8, 11, 9, 7],
                            backgroundColor: ["#0dcaf0", "#198754", "#6610f2", "#dc3545"],
                            borderRadius: 6,
                            maxBarThickness: 38,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false,
                        },
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            suggestedMax: 14,
                        },
                    },
                },
            })
        );
    }

    _disposeCharts() {
        this._charts.forEach((chart) => chart.destroy());
        this._charts = [];
    }
}

registry.category("actions").add("opportunities_dashboard", Dashboard);
