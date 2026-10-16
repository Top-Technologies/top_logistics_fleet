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
                // Fallback to CDN if core file didn't populate window.Chart
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

export class LogisticsDashboard extends Component {
    static template = "top_logistics_fleet.LogisticsDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.chartPipelineRef = useRef("chartPipeline");
        this.chartFleetStatusRef = useRef("chartFleetStatus");
        this.chartTrendsRef = useRef("chartTrends");
        this.chartSafetyRef = useRef("chartSafety");

        this._charts = {};

        this.state = useState({
            loading: true,
            refreshing: false,
            period: "all",
            activeTab: "overview", // 'overview' | 'requests' | 'fleet' | 'safety' | 'costs'
            data: null,
            error: null,
        });

        onMounted(() => this.loadData());
        onWillUnmount(() => this._destroyCharts());
    }

    async loadData() {
        this.state.loading = !this.state.data;
        this.state.refreshing = !!this.state.data;
        this.state.error = null;

        try {
            const result = await this.orm.call(
                "top.logistics.dashboard",
                "get_dashboard_data",
                [],
                { period: this.state.period }
            );
            this.state.data = result;
            this.state.loading = false;
            this.state.refreshing = false;

            await this._waitForDOM();
            await this._renderCharts();
        } catch (err) {
            console.error("[FMS Dashboard] Load error:", err);
            this.state.error = err.message || "Failed to load logistics dashboard data.";
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
        if (this.state.period === period) return;
        this.state.period = period;
        await this.loadData();
    }

    async setActiveTab(tab) {
        this.state.activeTab = tab;
        await this._waitForDOM();
        await this._renderCharts();
    }

    async refresh() {
        await this.loadData();
    }

    async _renderCharts() {
        if (!this.state.data) return;

        try {
            await loadChartJs();
        } catch (e) {
            console.warn("[FMS Dashboard] Chart.js could not be loaded:", e);
            return;
        }

        if (!window.Chart) return;

        this._destroyCharts();

        // 1. Pipeline Chart (Donut / Doughnut)
        if (this.chartPipelineRef.el && this.state.data.pipeline_chart) {
            const ctx = this.chartPipelineRef.el.getContext("2d");
            const pData = this.state.data.pipeline_chart;
            this._charts.pipeline = new window.Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: pData.labels,
                    datasets: [
                        {
                            data: pData.counts,
                            backgroundColor: pData.colors,
                            borderWidth: 2,
                            borderColor: "#ffffff",
                            hoverOffset: 6,
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
                                padding: 12,
                                font: { size: 11, weight: "600" },
                            },
                        },
                    },
                    cutout: "68%",
                },
            });
        }

        // 2. Fleet Status Chart (Doughnut)
        if (this.chartFleetStatusRef.el && this.state.data.fleet_chart) {
            const ctx = this.chartFleetStatusRef.el.getContext("2d");
            const fData = this.state.data.fleet_chart;
            this._charts.fleet = new window.Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: fData.labels,
                    datasets: [
                        {
                            data: fData.counts,
                            backgroundColor: fData.colors,
                            borderWidth: 2,
                            borderColor: "#ffffff",
                            hoverOffset: 6,
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
                                padding: 12,
                                font: { size: 11, weight: "600" },
                            },
                        },
                    },
                    cutout: "68%",
                },
            });
        }

        // 3. Weekly Trends Chart (Bar & Line Combo)
        if (this.chartTrendsRef.el && this.state.data.trend_chart) {
            const ctx = this.chartTrendsRef.el.getContext("2d");
            const tData = this.state.data.trend_chart;
            this._charts.trends = new window.Chart(ctx, {
                type: "bar",
                data: {
                    labels: tData.labels,
                    datasets: [
                        {
                            label: "Completed Trips",
                            data: tData.trips,
                            backgroundColor: "rgba(29, 78, 216, 0.75)",
                            borderRadius: 6,
                            yAxisID: "y",
                        },
                        {
                            label: "Distance (km)",
                            data: tData.distance,
                            type: "line",
                            borderColor: "#0891b2",
                            backgroundColor: "rgba(8, 145, 178, 0.1)",
                            tension: 0.35,
                            fill: true,
                            yAxisID: "y1",
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: "index",
                        intersect: false,
                    },
                    scales: {
                        y: {
                            type: "linear",
                            display: true,
                            position: "left",
                            title: { display: true, text: "Trips Count" },
                            grid: { color: "#f1f5f9" },
                        },
                        y1: {
                            type: "linear",
                            display: true,
                            position: "right",
                            title: { display: true, text: "Kilometers (km)" },
                            grid: { drawOnChartArea: false },
                        },
                    },
                    plugins: {
                        legend: {
                            position: "top",
                            labels: { boxWidth: 12, font: { size: 11, weight: "600" } },
                        },
                    },
                },
            });
        }

        // 4. Safety Events Chart (Horizontal Bar)
        if (this.chartSafetyRef.el && this.state.data.safety_chart) {
            const ctx = this.chartSafetyRef.el.getContext("2d");
            const sData = this.state.data.safety_chart;
            this._charts.safety = new window.Chart(ctx, {
                type: "bar",
                data: {
                    labels: sData.labels,
                    datasets: [
                        {
                            label: "Incidents & Telematics Events",
                            data: sData.counts,
                            backgroundColor: sData.colors,
                            borderRadius: 6,
                        },
                    ],
                },
                options: {
                    indexAxis: "y",
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            grid: { color: "#f1f5f9" },
                            ticks: { precision: 0 },
                        },
                    },
                    plugins: {
                        legend: { display: false },
                    },
                },
            });
        }
    }

    // ── Drill-down Handlers ──
    openRequests(domain = [], name = "Transport Requests") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "top.transport.request",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openTrips(domain = [], name = "Fleet Trips") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "top.fleet.trip",
            views: [[false, "list"], [false, "form"], [false, "calendar"]],
            domain: domain,
            target: "current",
        });
    }

    openVehicles(domain = [], name = "Fleet Vehicles") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "fleet.vehicle",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openGPSDevices(domain = [], name = "GPS Telematics Devices") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "top.gps.device",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openGPSEvents(domain = [], name = "GPS Safety & Telemetry Events") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "top.gps.event",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openFuelLogs(domain = [], name = "Fuel Transactions") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "top.fleet.fuel.log",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openAccidents(domain = [], name = "Accidents & Damage Reports") {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "top.fleet.accident",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openSingleRequest(requestId) {
        if (!requestId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "top.transport.request",
            res_id: requestId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSingleTrip(tripId) {
        if (!tripId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "top.fleet.trip",
            res_id: tripId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSingleVehicle(vehicleId) {
        if (!vehicleId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "fleet.vehicle",
            res_id: vehicleId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ── Quick Creation Shortcuts ──
    createNewRequest() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "New Transport Request",
            res_model: "top.transport.request",
            views: [[false, "form"]],
            target: "current",
        });
    }

    createNewTrip() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "New Trip Dispatch",
            res_model: "top.fleet.trip",
            views: [[false, "form"]],
            target: "current",
        });
    }

    createNewFuelLog() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Log Fuel Transaction",
            res_model: "top.fleet.fuel.log",
            views: [[false, "form"]],
            target: "new",
        });
    }

    createNewAccident() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Report Vehicle Accident / Incident",
            res_model: "top.fleet.accident",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openLiveMap() {
        this.action.doAction("top_logistics_fleet.action_top_fleet_live_map");
    }

    openAvailabilityCalendar() {
        this.action.doAction("top_logistics_fleet.action_top_vehicle_availability_calendar");
    }

    openVehicleDashboard() {
        this.action.doAction("top_logistics_fleet.action_top_vehicle_dashboard_client");
    }
}

registry.category("actions").add("top_logistics_fleet_dashboard", LogisticsDashboard);
