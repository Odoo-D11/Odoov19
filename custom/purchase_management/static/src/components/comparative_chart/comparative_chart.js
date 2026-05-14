/** @odoo-module **/

import { Component, onWillStart, useEffect, useRef, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const ACTION_TAG = "purchase_management_comparative_chart";

export class PurchaseManagementComparativeChart extends Component {
    static template = "purchase_management.PurchaseManagementComparativeChart";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.storageKey = "pm_comparative_chart_state";

        const resolveRecordState = () => {
            const params = this.props.action.params || {};
            const rfqId = params.request_quotation_id || null;
            if (rfqId) {
                const state = { id: parseInt(rfqId, 10) };
                sessionStorage.setItem(this.storageKey, JSON.stringify(state));
                return state;
            }
            try {
                const stored = sessionStorage.getItem(this.storageKey);
                return stored ? JSON.parse(stored) : { id: null };
            } catch {
                return { id: null };
            }
        };

        const { id } = resolveRecordState();
        this.recordId = id;
        this.rfqId = this.recordId; // alias para compatibilidad

        this.state = useState({
            kpis: {},
            tableData: { supplier_headers: [], rows: [], totals: {} },
            totalPriceChartData: {},
            validityChartData: {},
            productComparisonData: {},
            loading: true,
            error: null,
            searchQuery: "",
            currentPage: 1,
            itemsPerPage: 25,
            productView: "table",
            chartTypes: {
                productComparison: ['line', 'bar'],
                totalPrice: ['doughnut'],
                deliveryTime: ['bar'],
            },
            currentChartIndex: { productComparison: 0, totalPrice: 0, deliveryTime: 0 },
            filters: {
                product: { query: "", page: 1, selected: new Map(), list: [] },
                supplier: { query: "", page: 1, selected: new Map(), list: [] }
            },
            filterItemsPerPage: 5,
            suppliersInfo: [],
            allObservations: [],
            commercialTerms: [],
            currentObsIndex: 0,
            carouselPaused: false,
            chartFilterVersion: 0,
            customLegends: {
                totalPrice: [],
                validity: []
            },

            // Filtros de observaciones
            selectedSupplierId: null,
            obsFilters: {
                teams: new Set(),
                states: new Set()
            },
            filteredObservations: [],
            showObsFilterPopover: false,
            showObsInfoPopover: false,

            // Estado de la solicitud
            rfq_state: null,

        });

        this.productComparisonChartRef = useRef("productComparisonChart");
        this.productChartScrollContainerRef = useRef("productChartScrollContainer");
        this.customTooltipRef = useRef("customTooltip");
        this.charts = {};

        useEffect(() => {
            if (this.recordId) {
                const updateChannel = `quotation_line${this.recordId}`;
                this.busService.addChannel(updateChannel);
                const rejectChannel = `quotation_rejection_${this.recordId}`;
                this.busService.addChannel(rejectChannel);
                const notificationListener = async ({ detail: notifications }) => {
                    for (const { payload, type } of notifications) {
                        if (type === "quotation.quotation/update" && payload.quotation_id === this.recordId) {
                            if (!this._rejecting) {
                                try {
                                    await this.loadComparativeChartData();
                                } catch (e) {
                                    console.warn("Error recargando cuadro comparativo:", e);
                                }
                            }
                        }
                        if (type === "quotation.chart/rejected" && payload.id === this.recordId) {
                            this._rejecting = true;
                            this.busService.deleteChannel(`quotation_line${this.recordId}`);
                            this.busService.deleteChannel(`quotation_rejection_${this.recordId}`);
                        }
                    }
                };
                this.busService.addEventListener("notification", notificationListener);
            }
        }, () => [this.recordId]);

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            if (!this.recordId) {
                this.state.error = "No se pudo determinar la Solicitud.";
                this.state.loading = false;
                return;
            }
            await this.loadComparativeChartData();
        });

        useEffect(() => {
            if (!this.state.loading && !this.state.error) {
                this.renderCharts();
            }
        }, () => [
            this.state.loading, this.state.productView, this.state.chartFilterVersion,
            this.state.currentChartIndex.productComparison
        ]);

        onWillUnmount(() => {
            Object.values(this.charts).forEach(c => c && c.destroy());
            this.stopSlideshows();
        });
    }

    async redirectToForm() {
        try {
            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "request.quotation",
                res_id: this.recordId,
                view_mode: "form",
                views: [[false, "form"]],
                target: "main",
            }, {
                clear_breadcrumbs: true
            });
        } catch (error) {
            console.error("Error en redirección:", error);
            window.location.reload();
        }
    }

    get filteredTotals() {
        return this.state.tableData.totals || {};
    }

    get filteredRows() {
        const rows = (this.state.tableData && this.state.tableData.rows) ? this.state.tableData.rows : [];
        if (!this.state.searchQuery) return rows;
        return rows.filter(r => r.product_name.toLowerCase().includes(this.state.searchQuery.toLowerCase()));
    }

    get paginatedRows() {
        const rows = this.filteredRows;
        const start = (this.state.currentPage - 1) * this.state.itemsPerPage;
        return rows.slice(start, start + this.state.itemsPerPage);
    }

    get totalPages() {
        return Math.ceil(this.filteredRows.length / this.state.itemsPerPage);
    }

    get paginationInfo() {
        const total = this.filteredRows.length;
        if (total === 0) return "Sin resultados";
        const start = (this.state.currentPage - 1) * this.state.itemsPerPage + 1;
        const end = Math.min(this.state.currentPage * this.state.itemsPerPage, total);
        return `Mostrando ${start}-${end} de ${total}`;
    }

    goToPage(page) {
        if (page >= 1 && page <= this.totalPages) {
            this.state.currentPage = page;
        }
    }

    prevPage() {
        if (this.state.currentPage > 1) {
            this.state.currentPage--;
        }
    }

    nextPage() {
        if (this.state.currentPage < this.totalPages) {
            this.state.currentPage++;
        }
    }

    get visibleChartProductCount() {
        let count = 0;
        this.state.filters.product.selected.forEach(v => { if (v) count++ });
        if (count === 0 && this.state.filters.product.list) count = this.state.filters.product.list.length;
        return count;
    }

    async loadComparativeChartData() {
        if (this._rejecting) return;
        this.state.loading = true;
        try {
            const rpcParams = { request_quotation_id: this.recordId };
            const [comparativeChartData, rightsData] = await Promise.all([
                rpc("/purchase_management/get_comparative_chart_data", rpcParams),
                rpc("/purchase_management/get_approval_rights", rpcParams)
            ]);
            if (comparativeChartData.error) throw new Error(comparativeChartData.error);
            this.state.hasApprovalRights = rightsData.has_rights;

            this.state.kpis = this.formatKpis(comparativeChartData.kpis);

            this.state.tableData = comparativeChartData.tableData || { supplier_headers: [], rows: [], totals: {} };
            this.state.totalPriceChartData = comparativeChartData.totalPriceChartData || {};


            this.state.validityChartData = comparativeChartData.validityChartData || {};

            this.state.productComparisonData = comparativeChartData.productComparisonData || {};

            this.state.suppliersInfo = comparativeChartData.suppliersInfo || [];
            this.state.allObservations = comparativeChartData.allObservations || [];
            this.state.filteredObservations = [...this.state.allObservations];
            this.state.commercialTerms = comparativeChartData.commercialTerms || [];
            this.state.rfq_state = comparativeChartData.rfq_state || null;
            this.generateCustomLegends(this.state.totalPriceChartData, this.state.validityChartData);

            this.state.filters.product.list = comparativeChartData.productList || [];
            (comparativeChartData.productList || []).forEach(p => this.state.filters.product.selected.set(p.id, false));
            this.state.filters.supplier.list = comparativeChartData.supplierList || [];
            (comparativeChartData.supplierList || []).forEach(s => this.state.filters.supplier.selected.set(s.id, false));

            this.startSlideshows();

        } catch (error) {
            this.state.error = error.message;
            this.notification.add(this.state.error, { type: "danger" });
            console.error(error);
        } finally {
            this.state.loading = false;
        }
    }

    getInitials(name) {
        if (!name) return "";
        const parts = name.trim().split(" ").filter(p => p.length > 0);
        let initials = parts[0][0];
        if (parts.length > 1) {
            initials += parts[1][0];
        }
        return initials.toUpperCase();
    }

    get isRequestApproved() {
        return ['approved', 'order_created'].includes(this.state.rfq_state);
    }

    get awardedSuppliers() {
        return this.state.suppliersInfo.filter(s => s.is_awarded === true);
    }

    generateCustomLegends(priceData, validityData) {
        const priceLegend = [];
        if (priceData && priceData.labels && priceData.datasets && priceData.datasets[0]) {
            const values = priceData.datasets[0].data || [];
            const isCompleteList = priceData.datasets[0].is_complete || [];
            const mismatchList = priceData.datasets[0].has_qty_mismatch || [];
            const bgColors = priceData.datasets[0].backgroundColor || [];
            const borderColors = priceData.datasets[0].borderColor || [];
            const prices = values.slice(1).filter(v => v > 0);
            const minP = prices.length > 0 ? Math.min(...prices) : null;

            priceData.labels.forEach((label, index) => {
                const value = values[index];
                const isEstimated = label === 'Precio Estimado';

                let isBest = false;
                if (!isEstimated && value > 0) {
                    if (minP !== null && value === minP) isBest = true;
                }

                const isComplete = isCompleteList.length > index ? isCompleteList[index] : true;
                const hasMismatch = mismatchList.length > index ? mismatchList[index] : false;

                const priceSupplierInfo = this.state.suppliersInfo.find(s => s.name === label);
                const isPriceAwarded = this.isRequestApproved && (priceSupplierInfo ? priceSupplierInfo.is_awarded === true : false);

                priceLegend.push({
                    id: index,
                    name: label,
                    initials: isEstimated ? "PE" : this.getInitials(label),
                    value: this.formatCurrency(value),
                    rawValue: value,
                    bgColor: bgColors[index],
                    borderColor: borderColors[index],
                    isEstimated: isEstimated,
                    isBest: isBest,
                    isComplete: isComplete,
                    hasMismatch: hasMismatch,
                    isAwarded: isPriceAwarded,
                });
            });
        }
        this.state.customLegends.totalPrice = priceLegend.filter(i => !i.isEstimated);

        // LÓGICA DE VIGENCIA
        const validityLegend = [];

        // Aquí usamos la variable 'validityData' que recibimos como parámetro
        if (validityData && validityData.labels && validityData.datasets && validityData.datasets[0]) {
            const values = validityData.datasets[0].data || [];

            // Calcula el máximo para saber quién tiene la mayor vigencia
            const validValues = values.filter(v => v !== null && v !== undefined);
            const maxDays = validValues.length ? Math.max(...validValues) : -Infinity;

            const dates = validityData.validity_dates || []; // Asegúrate que en Python enviaste 'validity_dates'
            const bgColors = validityData.datasets[0].backgroundColor || [];
            const borderColors = validityData.datasets[0].borderColor || [];

            validityData.labels.forEach((label, index) => {
                const value = values[index];
                const date = dates[index] || 'N/A';

                const isExpired = (value !== null && value < 0);

                const supplierInfo = this.state.suppliersInfo.find(s => s.name === label);

                const isAwarded = this.isRequestApproved && (supplierInfo ? supplierInfo.is_awarded === true : false);

                validityLegend.push({
                    id: index,
                    name: label,
                    initials: this.getInitials(label),
                    rawValue: value !== null ? value : 'N/A',
                    displayValue: value !== null ? value : '-',
                    bgColor: bgColors[index],
                    borderColor: borderColors[index],
                    isBest: (value === maxDays && value !== null && !isExpired),
                    isExpired: isExpired,
                    dateStr: date,
                    isAwarded: isAwarded,
                });
            });
        }
        this.state.customLegends.validity = validityLegend;
    }

    startSlideshows() {
        this.stopSlideshows();

        if (this.state.allObservations && this.state.allObservations.length > 0) {
            this.obsInterval = setInterval(() => {
                if (!this.state.carouselPaused) this.nextObservation();
            }, 6000);
        }
    }

    stopSlideshows() {
        if (this.obsInterval) clearInterval(this.obsInterval);
    }

    renderCharts() {
        this.renderProductComparisonChart();
    }

    renderProductComparisonChart() {
        this.destroyChart('productComparison');
        if (!this.productComparisonChartRef.el || this.state.productView !== 'graph') return;

        const originalData = this.state.productComparisonData;
        if (!originalData.labels) return;

        let filteredIndices = [];
        let hasSelectedProducts = false;
        this.state.filters.product.selected.forEach((selected) => { if (selected) hasSelectedProducts = true; });

        if (!hasSelectedProducts) {
            filteredIndices = originalData.product_ids.map((_, i) => i);
        } else {
            originalData.product_ids.forEach((id, i) => {
                if (this.state.filters.product.selected.get(id)) filteredIndices.push(i);
            });
        }

        let hasSelectedSuppliers = false;
        this.state.filters.supplier.selected.forEach((selected) => { if (selected) hasSelectedSuppliers = true; });

        const finalDatasets = [];
        const finalSupplierIds = [];

        originalData.suppliers_ids.forEach((supplierId, index) => {
            if (!hasSelectedSuppliers || this.state.filters.supplier.selected.get(supplierId)) {
                const dataset = originalData.datasets[index];
                const relevantData = filteredIndices.map(i => dataset.data[i]);
                const hasRelevantData = relevantData.some(val => val !== null && val !== undefined && val > 0);
                if (!hasRelevantData) return;

                finalDatasets.push(dataset);
                finalSupplierIds.push(supplierId);
            }
        });

        const finalData = {
            labels: filteredIndices.map(i => originalData.labels[i]),
            all_product_details: filteredIndices.map(i => originalData.all_product_details[i]),
            suppliers_ids: finalSupplierIds,
            datasets: finalDatasets.map(d => ({
                ...d,
                data: filteredIndices.map(i => d.data[i]),
                is_best: d.is_best ? filteredIndices.map(i => d.is_best[i]) : undefined,
                qty_mismatch: d.qty_mismatch ? filteredIndices.map(i => d.qty_mismatch[i]) : undefined,
            }))
        };

        const ctx = this.productComparisonChartRef.el.getContext("2d");
        const chartType = (finalData.labels.length === 1) ? 'bar' : this.state.chartTypes.productComparison[this.state.currentChartIndex.productComparison];
        let options;
        const truncateLabelCallback = function (index) {
            const label = this.getLabelForValue(index);
            return (label && label.length > 15) ? label.substring(0, 15) + '...' : label;
        };

        if (chartType === 'line') {
            options = this.getLineChartOptions();
            if (options.scales && options.scales.x && options.scales.x.ticks) {
                options.scales.x.ticks.callback = truncateLabelCallback;
                options.scales.x.ticks.autoSkip = false;
            }

            finalData.datasets.forEach((d) => {
                d.no_quote_flags = [];
                d.data = d.data.map(value => {
                    if (value === null || value === undefined) {
                        d.no_quote_flags.push(true);
                        return 0;
                    }
                    d.no_quote_flags.push(false);
                    return value;
                });

                d.spanGaps = false;
                const isEstimated = d.label === 'Precio Estimado';
                if (isEstimated) {
                    d.borderDash = [5, 5];
                    d.backgroundColor = 'rgba(108, 117, 125, 0.2)';
                    d.fill = true;
                    d.tension = 0;
                    d.pointRadius = 3;
                } else {
                    d.tension = 0;
                    d.fill = true;
                    const [r, g, b] = (d.borderColor || 'rgba(0,0,0,1)').match(/\d+/g) || ['0', '0', '0'];
                    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
                    gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.4)`);
                    gradient.addColorStop(0.8, `rgba(${r}, ${g}, ${b}, 0)`);
                    d.backgroundColor = gradient;
                    d.borderWidth = 2;
                    d.pointRadius = (context) => {
                        const index = context.dataIndex;
                        if (d.no_quote_flags && d.no_quote_flags[index]) return 3;
                        return (d.is_best && d.is_best[index]) ? 5 : 3;
                    };
                }
            });
        } else {
            options = this.getBarChartOptions('x', { isCurrency: true });
            if (options.scales?.x?.ticks) {
                options.scales.x.ticks.callback = truncateLabelCallback;
                options.scales.x.ticks.autoSkip = false;
            }
            if (options.plugins?.legend) options.plugins.legend.display = false;

            finalData.datasets.forEach(dataset => {
                dataset.no_quote_flags = [];
                dataset.data = dataset.data.map(value => {
                    if (value === null || value === undefined) {
                        dataset.no_quote_flags.push(true);
                        return null;
                    }
                    dataset.no_quote_flags.push(false);
                    return value;
                });

                dataset.skipNull = true;
                dataset.barPercentage = 0.8;
                dataset.categoryPercentage = 0.9;

                const isEstimated = dataset.label === 'Precio Estimado';
                dataset.backgroundColor = isEstimated ? 'rgba(108, 117, 125, 0.2)' : dataset.borderColor.replace(', 1)', ', 0.2)');
                dataset.borderWidth = (context) => {
                    if (isEstimated) return 1;
                    return (dataset.is_best && dataset.is_best[context.dataIndex]) ? 3 : 1;
                };
                dataset.borderDash = isEstimated ? [5, 5] : [];
            });
        }

        options.plugins.tooltip = {
            enabled: false,
            external: this.externalTooltipHandler.bind(this),
            callbacks: {
                title: (context) => {
                    const productIndex = context[0].dataIndex;
                    const productName = finalData.labels[productIndex];
                    const productInfo = finalData.all_product_details[productIndex]['null'];
                    if (!productInfo || productInfo.requested_qty === 0) {
                        return `${productName} | Cantidad N/A`;
                    }
                    return `${productName} | ${productInfo.requested_qty} (${productInfo.uom})`;
                },
                label: (context) => ''
            }
        };

        this.charts['productComparison'] = new Chart(ctx, { type: chartType, data: finalData, options });
    }

    // Funciones de Tooltip para el gráfico de productos (sin cambios)
    positionAndShowTooltip(tooltipEl, chart, tooltip) {
        const canvasRect = chart.canvas.getBoundingClientRect();
        const tooltipWidth = tooltipEl.offsetWidth;
        const tooltipHeight = tooltipEl.offsetHeight;

        let left = canvasRect.left + window.pageXOffset + tooltip.caretX + 10;
        let top = canvasRect.top + window.pageYOffset + tooltip.caretY + 10;

        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        const scrollTop = window.pageYOffset;

        if (left + tooltipWidth > windowWidth - 20) {
            left = canvasRect.left + window.pageXOffset + tooltip.caretX - tooltipWidth - 10;
        }

        if ((top - scrollTop) + tooltipHeight > windowHeight - 20) {
            top = canvasRect.top + window.pageYOffset + tooltip.caretY - tooltipHeight - 10;
        }

        if (left < 10) left = 10;
        if (top < scrollTop + 10) top = scrollTop + 10;

        tooltipEl.style.left = `${left}px`;
        tooltipEl.style.top = `${top}px`;
        tooltipEl.style.opacity = 1;
    }

    externalTooltipHandler(context) {
        const { chart, tooltip } = context;
        const tooltipEl = this.customTooltipRef.el;

        if (!tooltipEl) return;

        if (tooltip.opacity === 0) {
            tooltipEl.style.opacity = 0;
            return;
        }

        let innerHtml = '';

        const titleLines = tooltip.title || [];
        if (titleLines.length > 0) {
            innerHtml += `<div class="pm-tooltip-header">${titleLines.join(' ')}</div>`;
        }

        const dataIndex = tooltip.dataPoints[0].dataIndex;
        const datasets = chart.data.datasets;

        // Calcula el mejor precio (mínimo) entre todos los proveedores para este producto
        let bestPrice = null;
        datasets.forEach(dataset => {
            const value = dataset.data[dataIndex];
            if (value !== null && value !== undefined && value > 0) {
                if (bestPrice === null || value < bestPrice) {
                    bestPrice = value;
                }
            }
        });

        if (tooltip.body.length > 0) {
            innerHtml += '<div class="pm-tooltip-separator"></div>';
            innerHtml += '<div class="pm-tooltip-body">';

            tooltip.dataPoints.forEach((dataPoint, i) => {
                const datasetIndex = dataPoint.datasetIndex;
                const dataset = datasets[datasetIndex];
                const providerLabel = dataset.label;

                const colors = tooltip.labelColors[i];
                const isNoQuote = dataset.no_quote_flags ? dataset.no_quote_flags[dataIndex] : false;
                const rawValue = dataset.data[dataIndex];
                const isBest = dataset.is_best ? dataset.is_best[dataIndex] : false;

                let supplierId = null;
                if (chart.data.suppliers_ids) {
                    supplierId = chart.data.suppliers_ids[datasetIndex];
                }

                let qtyInfo = null;
                if (chart.data.all_product_details) {
                    qtyInfo = chart.data.all_product_details[dataIndex][supplierId];
                }

                let priceDisplay = '';
                let mainLineBadge = '';
                let subLineContent = '';

                if (isNoQuote) {
                    mainLineBadge = `<span class="pm-tooltip-badge pm-badge-no-quote" style="margin-left: 8px;">NO COTIZÓ</span>`;
                } else {
                    priceDisplay = this.formatCurrency(rawValue);

                    let badgeHtml = '';
                    if (qtyInfo && qtyInfo.quoted_qty !== qtyInfo.requested_qty) {
                        badgeHtml = `<span class="pm-tooltip-badge pm-badge-warning" style="margin-left: 8px;">CANT. DIFERENTE</span>`;
                    } else if (isBest) {
                        badgeHtml = `<span class="pm-tooltip-badge pm-badge-best" style="margin-left: 8px;">MEJOR PRECIO</span>`;
                    }

                    let textHtml = '';
                    // Calcular costo extra comparando con el mejor precio
                    if (bestPrice !== null && rawValue !== null && !isBest && rawValue > 0) {
                        const extraCost = rawValue - bestPrice;
                        if (extraCost > 0) {
                            textHtml = `<span class="pm-tooltip-subline-text" style="margin-left: 8px;">(Costo Extra: ${this.formatCurrency(extraCost)})</span>`;
                        }
                    }
                    subLineContent = badgeHtml + textHtml;
                }

                innerHtml += `
                    <div class="pm-tooltip-line">
                        <div class="pm-tooltip-label-group">
                            <span class="pm-tooltip-color-box" style="background-color: ${colors.backgroundColor}; border-color: ${colors.borderColor};"></span>
                            <span class="pm-tooltip-label" title="${providerLabel}">${providerLabel}</span>
                        </div>
                        <span class="pm-tooltip-value">
                            ${isNoQuote ? mainLineBadge : priceDisplay}
                        </span>
                    </div>
                `;

                let sublineQty = '';
                if (!isNoQuote && qtyInfo && qtyInfo.quoted_qty > 0) {
                    sublineQty = `Cant: ${qtyInfo.quoted_qty} (${qtyInfo.uom})`;
                }

                if (sublineQty || subLineContent) {
                    innerHtml += `
                        <div class="pm-tooltip-subline">
                            <span class="pm-tooltip-subline-qty">${sublineQty}</span>
                            <span class="pm-tooltip-subline-status">
                                ${subLineContent}
                            </span>
                        </div>
                    `;
                }
            });
            innerHtml += '</div>';
        }

        tooltipEl.innerHTML = innerHtml;
        this.positionAndShowTooltip(tooltipEl, chart, tooltip);
    }

    formatCurrency(num) { return new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(num || 0); }
    formatTRM(num) {
        return new Intl.NumberFormat('es-CO', {
            style: 'currency',
            currency: 'COP',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(num || 0);
    }
    formatAxisNumber(num) { return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(num); }
    formatKpis(kpis) { const res = { ...kpis };['best_combination_total'].forEach(k => { res[k] = kpis[k] === 0 && k === 'best_offer_complete' ? 'N/A' : this.formatCurrency(kpis[k]); }); return res; }
    destroyChart(name) {
        if (this.charts[name]) { this.charts[name].destroy(); delete this.charts[name]; }
    }

    getMailToLink() {
        return 'mailto:';
    }

    async openQuotation(id) {
        if (id) await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "quotation.quotation",
            res_id: id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            name: "Odoo"
        });
    }

    nextObservation() {
        const length = this.state.filteredObservations.length || 1;
        this.state.currentObsIndex = (this.state.currentObsIndex + 1) % length;
        this.state.showObsInfoPopover = false;
    }
    prevObservation() {
        const length = this.state.filteredObservations.length || 1;
        this.state.currentObsIndex = (this.state.currentObsIndex - 1 + length) % length;
        this.state.showObsInfoPopover = false;
    }
    setCarouselPaused(p) {
        this.state.carouselPaused = p;
    }

    // Métodos de filtrado de observaciones
    applyObservationFilters() {
        const { teams, states } = this.state.obsFilters;
        const selectedSupplierId = this.state.selectedSupplierId;

        this.state.filteredObservations = this.state.allObservations.filter(obs => {
            // Filtro de proveedor 
            const matchSupplier = selectedSupplierId === null || obs.supplier_id === selectedSupplierId;
            // Filtro de equipo 
            const matchTeam = teams.size === 0 || teams.has(obs.team_key);
            // Filtro de estado 
            const matchState = states.size === 0 || states.has(obs.state);

            return matchSupplier && matchTeam && matchState;
        });
        if (this.state.currentObsIndex >= this.state.filteredObservations.length) {
            this.state.currentObsIndex = Math.max(0, this.state.filteredObservations.length - 1);
        }
    }

    selectSupplier(supplierId) {
        if (this.state.selectedSupplierId === supplierId) {
            this.state.selectedSupplierId = null;
        } else {
            this.state.selectedSupplierId = supplierId;
        }
        this.applyObservationFilters();
    }

    toggleObsFilter(filterType, value) {
        const filterSet = this.state.obsFilters[filterType];
        if (filterSet.has(value)) {
            filterSet.delete(value);
        } else {
            filterSet.add(value);
        }
        this.applyObservationFilters();
    }

    clearObsFilters() {
        this.state.selectedSupplierId = null;
        this.state.obsFilters.teams.clear();
        this.state.obsFilters.states.clear();
        this.applyObservationFilters();
    }

    toggleObsFilterPopover() {
        this.state.showObsFilterPopover = !this.state.showObsFilterPopover;
    }

    closeObsFilterPopover() {
        this.state.showObsFilterPopover = false;
    }

    toggleObsInfoPopover() {
        this.state.showObsInfoPopover = !this.state.showObsInfoPopover;
    }

    closeObsInfoPopover() {
        this.state.showObsInfoPopover = false;
    }

    getFilteredObservationsCount() {
        return this.state.filteredObservations.length;
    }

    getTotalObservationsCount() {
        return this.state.allObservations.length;
    }

    getActiveFiltersCount() {
        let count = 0;
        if (this.state.selectedSupplierId !== null) count++;
        count += this.state.obsFilters.teams.size;
        count += this.state.obsFilters.states.size;
        return count;
    }

    getFilterOptions(type) {
        const counts = new Map();
        const obsPool = this.state.allObservations;
        const selectedSupplierId = this.state.selectedSupplierId;

        const stateLabels = {
            'approved': 'Aprobado',
            'rejected': 'Rechazado',
            'recommended': 'Recomendado',
            'not_recommended': 'No Recomendado'
        };

        obsPool.forEach(obs => {
            if (selectedSupplierId !== null && obs.supplier_id !== selectedSupplierId) {
                return;
            }

            let key, name;
            if (type === 'teams') {
                key = obs.team_key;
                name = obs.team;
            } else {
                key = obs.state;
                name = stateLabels[obs.state] || obs.state;
            }

            if (!counts.has(key)) {
                counts.set(key, { key, name, count: 0 });
            }
            counts.get(key).count++;
        });

        // Retorna ordenado y solo los mayores a 0
        return Array.from(counts.values())
            .filter(item => item.count > 0)
            .sort((a, b) => a.name.localeCompare(b.name));
    }

    setProductView(view) { this.state.productView = view; }
    onSearchInput(ev) { this.state.searchQuery = ev.target.value; this.state.currentPage = 1; }
    getPaginatedList(type) { const filter = this.state.filters[type]; const query = filter.query.toLowerCase(); const filtered = filter.list.filter(item => item.name.toLowerCase().includes(query)); const start = (filter.page - 1) * this.state.filterItemsPerPage; return filtered.slice(start, start + this.state.filterItemsPerPage); }
    getTotalFilterPages(type) { const filter = this.state.filters[type]; const query = filter.query.toLowerCase(); const filtered = filter.list.filter(item => item.name.toLowerCase().includes(query)); return Math.ceil(filtered.length / this.state.filterItemsPerPage); }
    changeFilterPage(type, step) { const next = this.state.filters[type].page + step; if (next >= 1 && next <= this.getTotalFilterPages(type)) this.state.filters[type].page = next; }
    onFilterInput(type, ev) { this.state.filters[type].query = ev.target.value; this.state.filters[type].page = 1; }
    toggleFilterItem(type, id) { const map = this.state.filters[type].selected; map.set(id, !map.get(id)); this.state.chartFilterVersion++; }
    clearAll(type) { const map = this.state.filters[type].selected; map.forEach((_, id) => map.set(id, false)); this.state.chartFilterVersion++; }
    getProductChartContainerStyle() { let count = 0; this.state.filters.product.selected.forEach(v => { if (v) count++ }); if (count === 0) count = this.state.filters.product.list.length; const preferredChartType = this.state.chartTypes.productComparison[this.state.currentChartIndex.productComparison]; const actualChartType = (count === 1) ? 'bar' : preferredChartType; const minPx = actualChartType === 'bar' ? 200 : 160; const width = count * minPx; return `width: ${width}px; min-width: 100%; height: 100%; position: relative;`; }
    getBarChartOptions(indexAxis = 'x', { isCurrency = true } = {}) { const mainAxis = indexAxis === 'x' ? 'y' : 'x'; return { indexAxis, responsive: true, maintainAspectRatio: false, scales: { [mainAxis]: { beginAtZero: true, ticks: { callback: (val) => isCurrency ? this.formatAxisNumber(val) : val }, grid: { color: '#e9ecef', drawBorder: false } }, [indexAxis === 'x' ? 'x' : 'y']: { ticks: { autoSkip: false }, grid: { display: (indexAxis === 'y'), drawBorder: false } } }, plugins: { legend: { display: indexAxis === 'y', position: 'bottom' } } }; }

    getLineChartOptions() {
        return {
            indexAxis: 'x',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => this.formatAxisNumber(val)
                    },
                    grid: {
                        color: '#e9ecef',
                        drawBorder: false
                    }
                },
                x: {
                    ticks: {
                        autoSkip: false
                    },
                    grid: {
                        display: false
                    }
                }
            }, plugins: {
                legend: {
                    display: false
                }
            }, interaction: {
                mode: 'index',
                intersect: false
            }
        };
    }

    changeChartType(chartName, direction) {
        const types = this.state.chartTypes[chartName];
        const next = (this.state.currentChartIndex[chartName] + direction + types.length) % types.length;
        this.state.currentChartIndex[chartName] = next;
    }

    async approveQuotes() {
        try {
            const refreshComparativeChart = async () => {
                await new Promise(resolve => setTimeout(resolve, 300));
                await this.loadComparativeChartData();
            };

            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "approval.observation.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                name: "Odoo",
                context: { default_request_quotation_id: this.recordId, default_approval_mode: 'approve' }
            }, { onClose: refreshComparativeChart });
        } catch (error) {
            this.notification.add("Error al abrir el asistente de aprobación de cotizaciones.", { type: "danger" });
            console.error(error);
        }
    }

    async rejectQuotes() {
        try {
            this._rejecting = false;

            await this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: "reject.request.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
                name: "Odoo",
                context: { default_request_quotation_id: this.recordId, default_view: 'normal' }
            }, {
                onClose: async () => {
                    if (!this._rejecting) {
                        try {
                            await new Promise(resolve => setTimeout(resolve, 300));
                            if (!this._rejecting) {
                                await this.loadComparativeChartData();
                            }
                        } catch (e) {
                            console.warn("Error recargando los datos despues de cerrar wizard de rechazo:", e);
                        }
                    }
                    this._rejecting = false;
                }
            });
        } catch (error) {
            this.notification.add("Error al abrir el asistente de rechazo de cotizaciones.", { type: "danger" });
            console.error(error);
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

registry.category("actions").add(ACTION_TAG, PurchaseManagementComparativeChart);