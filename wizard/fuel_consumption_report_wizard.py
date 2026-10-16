# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FuelConsumptionReportWizard(models.TransientModel):
    _name = 'top.fuel.consumption.report.wizard'
    _description = 'Fuel Consumption & Efficiency Telematics Report Wizard'

    report_type = fields.Selection([
        ('daily', 'Daily Report (Today)'),
        ('weekly', 'Weekly Report (This Week)'),
        ('monthly', 'Monthly Report (This Month)'),
        ('custom', 'Custom Date Range'),
    ], string='Reporting Period', default='weekly', required=True)

    date_from = fields.Datetime(string='Start Date & Time', required=True,
                                default=lambda self: fields.Datetime.now() - timedelta(days=7))
    date_to = fields.Datetime(string='End Date & Time', required=True,
                              default=fields.Datetime.now)

    vehicle_ids = fields.Many2many(
        'fleet.vehicle',
        string='Vehicles to Include',
        help='Leave empty to include all 16 GPS-monitored fleet vehicles.',
    )

    include_transactions = fields.Boolean(
        string='Include GPS Fuel Transactions (Refills & Drains)',
        default=True,
        help='Include the detailed audit table of GPS-detected fuel refills and sudden fuel drop/theft alerts.',
    )

    @api.onchange('report_type')
    def _onchange_report_type(self):
        now = fields.Datetime.now()
        today_date = fields.Date.context_today(self)
        
        if self.report_type == 'daily':
            start = datetime.combine(today_date, time.min)
            end = datetime.combine(today_date, time.max)
            self.date_from = start
            self.date_to = end
        elif self.report_type == 'weekly':
            # Start of current week (Monday)
            start_week = today_date - timedelta(days=today_date.weekday())
            self.date_from = datetime.combine(start_week, time.min)
            self.date_to = now
        elif self.report_type == 'monthly':
            # Start of current month
            start_month = today_date.replace(day=1)
            self.date_from = datetime.combine(start_month, time.min)
            self.date_to = now
        elif self.report_type == 'custom':
            if not self.date_from:
                self.date_from = now - timedelta(days=7)
            if not self.date_to:
                self.date_to = now

    def _get_target_vehicles(self):
        if self.vehicle_ids:
            return self.vehicle_ids
        # All vehicles with a linked GPS device
        devices = self.env['top.gps.device'].search([('vehicle_id', '!=', False)])
        return devices.mapped('vehicle_id') or self.env['fleet.vehicle'].search([])

    def action_generate_analytics(self):
        """Computes telematics data and opens interactive Pivot, Graph, and List views."""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("Start Date cannot be later than End Date."))

        vehicles = self._get_target_vehicles()
        analyses = self.env['top.fleet.fuel.analysis'].compute_telematics_data(
            self.date_from,
            self.date_to,
            vehicles,
            self.report_type
        )

        return {
            'name': _('Fleet Fuel Consumption & Efficiency Analytics (%s)') % dict(
                self._fields['report_type'].selection
            ).get(self.report_type, 'Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.fleet.fuel.analysis',
            'view_mode': 'pivot,graph,list,form',
            'domain': [('id', 'in', analyses.ids)],
            'context': {
                'search_default_group_by_vehicle': 1,
            },
        }

    def action_print_pdf(self):
        """Computes telematics data and renders the professional executive PDF report."""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_("Start Date cannot be later than End Date."))

        vehicles = self._get_target_vehicles()
        self.env['top.fleet.fuel.analysis'].compute_telematics_data(
            self.date_from,
            self.date_to,
            vehicles,
            self.report_type
        )
        return self.env.ref('top_logistics_fleet.action_report_fleet_fuel_efficiency_pdf').report_action(self)

    def action_view_transactions(self):
        """Computes and opens GPS-detected fuel refills and drain events."""
        self.ensure_one()
        vehicles = self._get_target_vehicles()
        self.env['top.fleet.fuel.analysis'].compute_telematics_data(
            self.date_from,
            self.date_to,
            vehicles,
            self.report_type
        )
        return {
            'name': _('GPS Fuel Transactions (Refills & Drains)'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.gps.fuel.transaction',
            'view_mode': 'list,form',
            'domain': [
                ('vehicle_id', 'in', vehicles.ids),
                ('timestamp', '>=', self.date_from),
                ('timestamp', '<=', self.date_to),
            ],
            'context': {'search_default_group_by_vehicle': 1},
        }

    def get_report_data(self):
        """Helper called by the QWeb report template to get aggregated metrics and rows."""
        self.ensure_one()
        vehicles = self._get_target_vehicles()
        analyses = self.env['top.fleet.fuel.analysis'].search([
            ('vehicle_id', 'in', vehicles.ids),
            ('date_from', '=', self.date_from),
            ('date_to', '=', self.date_to),
        ], order='distance_km desc, vehicle_id')

        # Overall summary cards
        total_distance = sum(analyses.mapped('distance_km'))
        total_fuel_consumed = sum(analyses.mapped('fuel_consumed'))
        total_refueled = sum(analyses.mapped('total_refueled'))
        total_drained = sum(analyses.mapped('total_drained'))
        avg_rate = round((total_fuel_consumed / total_distance * 100.0), 2) if total_distance > 0 else 0.0
        
        # GPS Transactions in period
        transactions = self.env['top.gps.fuel.transaction'].search([
            ('vehicle_id', 'in', vehicles.ids),
            ('timestamp', '>=', self.date_from),
            ('timestamp', '<=', self.date_to),
        ], order='timestamp desc')

        return {
            'wizard': self,
            'analyses': analyses,
            'transactions': transactions,
            'total_vehicles': len(analyses),
            'total_distance': total_distance,
            'total_fuel_consumed': total_fuel_consumed,
            'total_refueled': total_refueled,
            'total_drained': total_drained,
            'avg_rate': avg_rate,
            'refuel_count': len(transactions.filtered(lambda t: t.transaction_type == 'refuel')),
            'drain_count': len(transactions.filtered(lambda t: t.transaction_type == 'drain')),
        }
