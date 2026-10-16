/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";

function loadChartJs() {
    return new Promise((resolve, reject) => {
        if (window.Chart) {
            resolve();
            return;
        }
        const existing = document.querySelector('script[src*="Chart.js"], script[src*="chart.js"], script[src*="chart.umd"]');
        if (existing) {
            existing.addEventListener("load", resolve);
            existing.addEventListener("error", reject);
            return;
        }
        const script = document.createElement("script");
        script.src = "/web/static/lib/Chart/Chart.js";
        script.onload = () => {
            if (window.Chart) {
                resolve();
            } else {
                const cdn = document.createElement("script");
                cdn.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
                cdn.onload = resolve;
                cdn.onerror = reject;
                document.head.appendChild(cdn);
            }
        };
        script.onerror = () => {
            const cdn = document.createElement("script");
            cdn.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";
            cdn.onload = resolve;
            cdn.onerror = reject;
            document.head.appendChild(cdn);
        };
        document.head.appendChild(script);
    });
}

export class VehicleDashboard extends Component {
    static template = "top_logistics_fleet.VehicleDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.fuelChartRef = useRef("fuelEfficiencyChart");
        this.distanceChartRef = useRef("distanceOverTimeChart");
        this.utilGaugeRef = useRef("utilizationGaugeChart");
        this.statusGaugeRef = useRef("vehicleStatusGaugeChart");

        this.hourlyChartRef = useRef("hourlyFuelChart");
        this.minuteChartRef = useRef("minuteFuelChart");

        this._charts = {};

        const today = new Date();
        const past7 = new Date(today);
        past7.setDate(past7.getDate() - 7);
        const toIso = (d) => d.toISOString().split("T")[0];

        this.state = useState({
            loading: true,
            refreshing: false,
            period: "daily", // 'daily' | 'weekly' | 'monthly' | 'custom'
            customDateFrom: toIso(past7),
            customDateTo: toIso(today),
            showCustomDateInputs: false,
            statusFilter: "all", // 'all' | 'available' | 'active' | 'maintenance' | 'inactive'
            searchQuery: "",
            data: null,
            error: null,

            // Telematics Drill-down Drawer
            drawerOpen: false,
            drawerLoading: false,
            drawerTab: "hourly", // 'hourly' | 'minute'
            selectedVehicle: null,
            drawerData: null,
        });

        onMounted(() => this.loadData());
        onWillUnmount(() => this._destroyCharts());
    }

    async loadData() {
        this.state.loading = !this.state.data;
        this.state.refreshing = !!this.state.data;
        this.state.error = null;

        try {
            const params = { period: this.state.period };
            if (this.state.period === "custom") {
                params.date_from = this.state.customDateFrom;
                params.date_to = this.state.customDateTo;
            }
            const result = await this.orm.call(
                "top.logistics.dashboard",
                "get_vehicle_analytics_data",
                [],
                params
            );
            this.state.data = result;
            this.state.loading = false;
            this.state.refreshing = false;

            await this._waitForDOM();
            await this._renderCharts();
        } catch (err) {
            console.error("[Vehicle Dashboard] Load error:", err);
            this.state.error = err.message || "Failed to load vehicle analytics data.";
            this.state.loading = false;
            this.state.refreshing = false;
        }
    }

    _waitForDOM() {
        return new Promise((resolve) => {
            requestAnimationFrame(() => {
                requestAnimationFrame(resolve);
            });
        });
    }

    _destroyCharts() {
        Object.values(this._charts).forEach((chart) => {
            if (chart && typeof chart.destroy === "function") {
                chart.destroy();
            }
        });
        this._charts = {};
    }

    async setPeriod(period) {
        if (period === "custom") {
            this.state.showCustomDateInputs = true;
            this.state.period = "custom";
            await this.loadData();
            return;
        }
        this.state.showCustomDateInputs = false;
        if (this.state.period === period) return;
        this.state.period = period;
        await this.loadData();
    }

    toggleCustomDateInputs() {
        this.state.showCustomDateInputs = !this.state.showCustomDateInputs;
        if (this.state.showCustomDateInputs) {
            this.state.period = "custom";
        }
    }

    onCustomDateChange(type, value) {
        if (type === "from") {
            this.state.customDateFrom = value;
        } else {
            this.state.customDateTo = value;
        }
    }

    async applyCustomDateRange() {
        if (!this.state.customDateFrom || !this.state.customDateTo) return;
        this.state.period = "custom";
        await this.loadData();
    }

    setStatusFilter(status) {
        this.state.statusFilter = status;
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value.toLowerCase().trim();
    }

    get filteredPerformanceRecords() {
        if (!this.state.data || !this.state.data.performance_records) {
            return [];
        }
        return this.state.data.performance_records.filter((rec) => {
            if (this.state.statusFilter !== "all" && rec.status_cls !== this.state.statusFilter) {
                return false;
            }
            if (this.state.searchQuery) {
                const q = this.state.searchQuery;
                const matchCode = rec.code && rec.code.toLowerCase().includes(q);
                const matchName = rec.name && rec.name.toLowerCase().includes(q);
                const matchType = rec.type && rec.type.toLowerCase().includes(q);
                return matchCode || matchName || matchType;
            }
            return true;
        });
    }

    async refresh() {
        await this.loadData();
    }

    openControlCenter() {
        this.action.doAction("top_logistics_fleet.action_top_logistics_dashboard_client");
    }

    openVehicleList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "fleet.vehicle",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openVehicleRecord(vehicleId) {
        if (!vehicleId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "fleet.vehicle",
            res_id: vehicleId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTrips() {
        this.action.doAction("top_logistics_fleet.action_top_fleet_trip_all");
    }

    openFuelLogs() {
        this.action.doAction("top_logistics_fleet.action_top_fleet_fuel_analysis");
    }

    // ── Telematics Drill-Down Drawer Methods ──
    async openVehicleTelemetry(vehicle) {
        this.state.selectedVehicle = vehicle;
        this.state.drawerOpen = true;
        this.state.drawerLoading = true;
        this.state.drawerData = null;

        try {
            const params = {
                vehicle_id: vehicle.id,
            };
            if (this.state.period === "custom") {
                params.date_from = this.state.customDateFrom + " 00:00:00";
                params.date_to = this.state.customDateTo + " 23:59:59";
            }
            const data = await this.orm.call(
                "top.logistics.dashboard",
                "get_vehicle_fuel_telemetry",
                [],
                params
            );
            this.state.drawerData = data;
            this.state.drawerLoading = false;

            await this._waitForDOM();
            await this._renderDrawerCharts();
        } catch (err) {
            console.error("[Vehicle Dashboard] Telemetry error:", err);
            this.state.drawerLoading = false;
        }
    }

    closeDrawer() {
        this.state.drawerOpen = false;
        if (this._charts.hourly) {
            this._charts.hourly.destroy();
            delete this._charts.hourly;
        }
        if (this._charts.minute) {
            this._charts.minute.destroy();
            delete this._charts.minute;
        }
    }

    async setDrawerTab(tab) {
        if (this.state.drawerTab === tab) return;
        this.state.drawerTab = tab;
        await this._waitForDOM();
        await this._renderDrawerCharts();
    }

    async _renderDrawerCharts() {
        if (!this.state.drawerData) return;
        try {
            await loadChartJs();
        } catch (e) {
            return;
        }
        if (!window.Chart) return;

        if (this.state.drawerTab === "hourly" && this.hourlyChartRef.el) {
            if (this._charts.hourly) {
                this._charts.hourly.destroy();
            }
            const ctx = this.hourlyChartRef.el.getContext("2d");
            const buckets = this.state.drawerData.hourly_buckets || [];
            this._charts.hourly = new window.Chart(ctx, {
                type: "bar",
                data: {
                    labels: buckets.map((b) => b.hour),
                    datasets: [
                        {
                            label: "Driving Fuel (L)",
                            data: buckets.map((b) => b.driving_fuel),
                            backgroundColor: "#2563eb",
                            borderRadius: 4,
                            stack: "fuel",
                        },
                        {
                            label: "Idling Fuel (L)",
                            data: buckets.map((b) => b.idling_fuel),
                            backgroundColor: "#f59e0b",
                            borderRadius: 4,
                            stack: "fuel",
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "top" },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} L`,
                            },
                        },
                    },
                    scales: {
                        x: { stacked: true, grid: { display: false } },
                        y: {
                            stacked: true,
                            beginAtZero: true,
                            grid: { color: "#f1f5f9" },
                            title: { display: true, text: "Litres (L)" },
                        },
                    },
                },
            });
        } else if (this.state.drawerTab === "minute" && this.minuteChartRef.el) {
            if (this._charts.minute) {
                this._charts.minute.destroy();
            }
            const ctx = this.minuteChartRef.el.getContext("2d");
            const series = this.state.drawerData.minute_series || { labels: [], smoothed_fuel: [], raw_fuel: [] };
            this._charts.minute = new window.Chart(ctx, {
                type: "line",
                data: {
                    labels: series.labels,
                    datasets: [
                        {
                            label: "Smoothed Tank Level (L)",
                            data: series.smoothed_fuel,
                            borderColor: "#059669",
                            backgroundColor: "rgba(5, 150, 105, 0.08)",
                            borderWidth: 2.5,
                            tension: 0.3,
                            fill: true,
                            pointRadius: 2,
                            pointHoverRadius: 6,
                        },
                        {
                            label: "Raw Sensor Reading (L)",
                            data: series.raw_fuel,
                            borderColor: "#94a3b8",
                            borderWidth: 1,
                            borderDash: [3, 3],
                            pointRadius: 0,
                            fill: false,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "top" },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} L`,
                            },
                        },
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: {
                            beginAtZero: false,
                            grid: { color: "#f1f5f9" },
                            title: { display: true, text: "Fuel Tank Level (L)" },
                        },
                    },
                },
            });
        }
    }

    async _renderCharts() {
        if (!this.state.data) return;

        try {
            await loadChartJs();
        } catch (e) {
            console.warn("[Vehicle Dashboard] Chart.js could not be loaded:", e);
            return;
        }

        if (!window.Chart) return;

        this._destroyCharts();

        // 1. Fuel Efficiency Chart (Bar Chart with vibrant orange bars)
        if (this.fuelChartRef.el && this.state.data.fuel_chart) {
            const ctx = this.fuelChartRef.el.getContext("2d");
            const fData = this.state.data.fuel_chart;
            this._charts.fuel = new window.Chart(ctx, {
                type: "bar",
                data: {
                    labels: fData.labels,
                    datasets: [
                        {
                            label: "Efficiency (km/L)",
                            data: fData.values,
                            backgroundColor: "#ff6b00",
                            borderRadius: 6,
                            barPercentage: 0.35,
                            order: 1,
                        },
                        {
                            label: "Baseline",
                            data: fData.bg_values,
                            backgroundColor: "#f1f5f9",
                            borderRadius: 6,
                            barPercentage: 0.35,
                            order: 2,
                            hoverBackgroundColor: "#f1f5f9",
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            filter: (item) => item.datasetIndex === 0,
                            callbacks: {
                                label: (ctx) => `Efficiency: ${ctx.raw} km/L`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, weight: "500" }, color: "#64748b" },
                        },
                        y: {
                            border: { dash: [4, 4] },
                            grid: { color: "#f1f5f9" },
                            ticks: {
                                stepSize: 20,
                                font: { size: 11 },
                                color: "#94a3b8",
                            },
                            beginAtZero: true,
                        },
                    },
                },
            });
        }

        // 2. Distance Over Time Chart (Line + Bar combo)
        if (this.distanceChartRef.el && this.state.data.distance_chart) {
            const ctx = this.distanceChartRef.el.getContext("2d");
            const dData = this.state.data.distance_chart;
            this._charts.distance = new window.Chart(ctx, {
                data: {
                    labels: dData.labels,
                    datasets: [
                        {
                            type: "line",
                            label: "Trend (km)",
                            data: dData.line_values,
                            borderColor: "#3b82f6",
                            backgroundColor: "rgba(59, 130, 246, 0.08)",
                            borderWidth: 2.5,
                            tension: 0.38,
                            fill: true,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            order: 1,
                        },
                        {
                            type: "bar",
                            label: "Distance (km)",
                            data: dData.bar_values,
                            backgroundColor: (ctx) => {
                                const idx = ctx.dataIndex;
                                return idx >= 3 ? "#ff6b00" : "#e2e8f0";
                            },
                            borderRadius: 4,
                            barPercentage: 0.32,
                            order: 2,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.dataset.label}: ${ctx.raw} km`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { font: { size: 11, weight: "500" }, color: "#64748b" },
                        },
                        y: {
                            border: { dash: [4, 4] },
                            grid: { color: "#f1f5f9" },
                            ticks: {
                                stepSize: 20,
                                font: { size: 11 },
                                color: "#94a3b8",
                            },
                            beginAtZero: true,
                        },
                    },
                },
            });
        }

        // 3. Utilization Semi-Doughnut Gauge (180 degree arch)
        if (this.utilGaugeRef.el && this.state.data.utilization_gauge) {
            const ctx = this.utilGaugeRef.el.getContext("2d");
            const uData = this.state.data.utilization_gauge;
            this._charts.utilization = new window.Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: ["Active", "Idle", "Inactive"],
                    datasets: [
                        {
                            data: [
                                uData.active_count || 0.1,
                                uData.idle_count || 0.1,
                                uData.inactive_count || 0.1,
                            ],
                            backgroundColor: ["#3b82f6", "#ff9800", "#e2e8f0"],
                            borderWidth: 0,
                            cutout: "78%",
                            circumference: 180,
                            rotation: -90,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: true },
                    },
                },
            });
        }

        // 4. Vehicle Status Semi-Doughnut Gauge (180 degree arch)
        if (this.statusGaugeRef.el && this.state.data.status_gauge) {
            const ctx = this.statusGaugeRef.el.getContext("2d");
            const sData = this.state.data.status_gauge;
            this._charts.status = new window.Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: ["Active", "Maintenance", "Inactive"],
                    datasets: [
                        {
                            data: [
                                sData.active_count || 0.1,
                                sData.maintenance_count || 0.1,
                                sData.inactive_count || 0.1,
                            ],
                            backgroundColor: ["#ff6b00", "#3b82f6", "#e2e8f0"],
                            borderWidth: 0,
                            cutout: "78%",
                            circumference: 180,
                            rotation: -90,
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: { enabled: true },
                    },
                },
            });
        }
    }
}

registry.category("actions").add("top_vehicle_dashboard", VehicleDashboard);
