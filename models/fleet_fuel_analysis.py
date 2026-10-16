# -*- coding: utf-8 -*-
from datetime import datetime, time
from odoo import api, fields, models, _


class FleetFuelAnalysis(models.Model):
    _name = 'top.fleet.fuel.analysis'
    _description = 'Vehicle Telematics Fuel & Efficiency Analysis'
    _order = 'date_from desc, vehicle_id, id desc'

    name = fields.Char(string='Summary Period', required=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, index=True)
    license_plate = fields.Char(related='vehicle_id.license_plate', string='License Plate', store=True)
    device_id = fields.Many2one('top.gps.device', string='GPS Tracker', index=True)
    driver_id = fields.Many2one('hr.employee', string='Default Driver')

    period_type = fields.Selection([
        ('daily', 'Daily Breakdown'),
        ('weekly', 'Weekly Summary'),
        ('monthly', 'Monthly Summary'),
        ('custom', 'Custom Date Range'),
    ], string='Period Granularity', default='daily', required=True, index=True)

    date = fields.Date(string='Reference Date', index=True)
    date_from = fields.Datetime(string='Start Timestamp', required=True, index=True)
    date_to = fields.Datetime(string='End Timestamp', required=True, index=True)

    # Odometer & Distance
    start_odometer = fields.Float(string='Start Odometer (km)', digits=(10, 1))
    end_odometer = fields.Float(string='End Odometer (km)', digits=(10, 1))
    distance_km = fields.Float(string='Distance Traveled (km)', digits=(10, 1), index=True)

    # Tank Level & Refuel Metrics
    start_fuel = fields.Float(string='Start Tank Level (L)', digits=(10, 2))
    end_fuel = fields.Float(string='End Tank Level (L)', digits=(10, 2))
    total_refueled = fields.Float(string='Total Refueled (L)', digits=(10, 2))
    refuel_count = fields.Integer(string='Refills Count')
    total_drained = fields.Float(string='Fuel Drain / Drops (L)', digits=(10, 2))
    drain_count = fields.Integer(string='Drain Alerts Count')

    # Fuel Consumed & Efficiency
    fuel_consumed = fields.Float(string='Fuel Consumed (L)', digits=(10, 2), index=True)
    consumption_rate = fields.Float(string='Rate (L/100km)', digits=(10, 2), index=True,
                                    help='Litres of fuel consumed per 100 kilometers.')
    fuel_economy = fields.Float(string='Economy (km/L)', digits=(10, 2),
                                help='Kilometers traveled per litre of fuel.')
    benchmark_rate = fields.Float(string='Standard Norm (L/100km)', digits=(10, 2),
                                  help='Standard expected consumption rate from vehicle settings.')
    variance_pct = fields.Float(string='Variance vs Norm (%)', digits=(10, 1),
                                help='Percentage difference between actual consumption rate and standard norm.')

    efficiency_status = fields.Selection([
        ('efficient', 'Fuel Efficient (< Norm)'),
        ('normal', 'Normal Standard (Within +/- 15%)'),
        ('high', 'High Consumption (> 15% Norm)'),
        ('alert', 'Theft Alert / Abnormal Drain'),
    ], string='Efficiency Rating', default='normal', index=True)

    theft_suspected = fields.Boolean(string='Theft / Drain Flagged', index=True)

    @api.model
    def compute_telematics_data(self, date_from, date_to, vehicle_ids=None, period_type='custom'):
        """
        Analyzes GPS telemetry from top.gps.position for the given date range and vehicles.
        Populates top.fleet.fuel.analysis and auto-detects top.gps.fuel.transaction records.
        Returns the created/updated analysis recordset.
        """
        Position = self.env['top.gps.position']
        Vehicle = self.env['fleet.vehicle']
        Transaction = self.env['top.gps.fuel.transaction']

        if not vehicle_ids:
            # Query all vehicles that have a linked GPS device
            devices = self.env['top.gps.device'].search([('vehicle_id', '!=', False)])
            vehicle_ids = devices.mapped('vehicle_id')
        elif isinstance(vehicle_ids, (list, tuple)):
            vehicle_ids = Vehicle.browse(vehicle_ids)

        created_records = self.env['top.fleet.fuel.analysis']

        for vehicle in vehicle_ids:
            device = vehicle.gps_device_id
            if not device:
                # Find device if not directly set
                device = self.env['top.gps.device'].search([('vehicle_id', '=', vehicle.id)], limit=1)

            positions = Position.search([
                ('vehicle_id', '=', vehicle.id),
                ('timestamp', '>=', date_from),
                ('timestamp', '<=', date_to),
            ], order='timestamp ASC, id ASC')

            if not positions:
                # Fallback check by device_id if vehicle_id was unset on some old position records
                if device:
                    positions = Position.search([
                        ('device_id', '=', device.id),
                        ('timestamp', '>=', date_from),
                        ('timestamp', '<=', date_to),
                    ], order='timestamp ASC, id ASC')

            if not positions:
                continue

            first_pos = positions[0]
            last_pos = positions[-1]

            start_odo = first_pos.odometer or 0.0
            end_odo = last_pos.odometer or 0.0
            distance = max(0.0, round(end_odo - start_odo, 2))

            start_fuel = float(first_pos.fuel_level or 0.0)
            end_fuel = float(last_pos.fuel_level or 0.0)

            total_refueled = 0.0
            refuel_count = 0
            total_drained = 0.0
            drain_count = 0

            prev_fuel = start_fuel

            for pos in positions[1:]:
                curr_fuel = float(pos.fuel_level or 0.0)
                diff = curr_fuel - prev_fuel

                # Refuel detection threshold: >= 10.0 Litres increase
                if diff >= 10.0:
                    total_refueled += diff
                    refuel_count += 1
                    # Check if transaction already logged
                    existing = Transaction.search([
                        ('vehicle_id', '=', vehicle.id),
                        ('transaction_type', '=', 'refuel'),
                        ('timestamp', '=', pos.timestamp),
                    ], limit=1)
                    if not existing:
                        Transaction.create({
                            'transaction_type': 'refuel',
                            'timestamp': pos.timestamp,
                            'vehicle_id': vehicle.id,
                            'device_id': device.id if device else False,
                            'driver_id': vehicle.driver_id.id if vehicle.driver_id else False,
                            'initial_fuel': round(prev_fuel, 2),
                            'final_fuel': round(curr_fuel, 2),
                            'volume': round(diff, 2),
                            'odometer': pos.odometer,
                            'speed': pos.speed,
                            'latitude': pos.latitude,
                            'longitude': pos.longitude,
                            'address': pos.address,
                            'state': 'detected',
                        })

                # Sudden drain / theft detection threshold: >= 10.0 Litres drop while speed <= 10 km/h
                elif diff <= -10.0 and (pos.speed or 0.0) <= 10.0:
                    loss = abs(diff)
                    total_drained += loss
                    drain_count += 1
                    existing = Transaction.search([
                        ('vehicle_id', '=', vehicle.id),
                        ('transaction_type', '=', 'drain'),
                        ('timestamp', '=', pos.timestamp),
                    ], limit=1)
                    if not existing:
                        Transaction.create({
                            'transaction_type': 'drain',
                            'timestamp': pos.timestamp,
                            'vehicle_id': vehicle.id,
                            'device_id': device.id if device else False,
                            'driver_id': vehicle.driver_id.id if vehicle.driver_id else False,
                            'initial_fuel': round(prev_fuel, 2),
                            'final_fuel': round(curr_fuel, 2),
                            'volume': round(loss, 2),
                            'odometer': pos.odometer,
                            'speed': pos.speed,
                            'latitude': pos.latitude,
                            'longitude': pos.longitude,
                            'address': pos.address,
                            'state': 'flagged',
                        })

                prev_fuel = curr_fuel

            # Consumed fuel = (Start Fuel + Refueled) - End Fuel
            consumed = max(0.0, round((start_fuel + total_refueled) - end_fuel, 2))
            
            # Rate L/100km
            rate = round((consumed / distance * 100.0), 2) if distance > 0.0 else 0.0
            economy = round(distance / consumed, 2) if consumed > 0.0 else 0.0
            benchmark = vehicle.expected_fuel_consumption or 45.0

            variance = round(((rate - benchmark) / benchmark * 100.0), 1) if (benchmark > 0.0 and rate > 0.0) else 0.0

            theft_flag = bool(drain_count > 0 or (rate > benchmark * 1.4 and distance > 50.0))

            if theft_flag:
                status = 'alert'
            elif rate <= benchmark * 0.9 and rate > 0.0:
                status = 'efficient'
            elif rate > benchmark * 1.15:
                status = 'high'
            else:
                status = 'normal'

            period_label = f"{vehicle.name} [{date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')}]"

            # Check if analysis record already exists for this vehicle & period
            rec = self.search([
                ('vehicle_id', '=', vehicle.id),
                ('period_type', '=', period_type),
                ('date_from', '=', date_from),
                ('date_to', '=', date_to),
            ], limit=1)

            vals = {
                'name': period_label,
                'vehicle_id': vehicle.id,
                'device_id': device.id if device else False,
                'driver_id': vehicle.driver_id.id if vehicle.driver_id else False,
                'period_type': period_type,
                'date': date_from.date(),
                'date_from': date_from,
                'date_to': date_to,
                'start_odometer': start_odo,
                'end_odometer': end_odo,
                'distance_km': distance,
                'start_fuel': start_fuel,
                'end_fuel': end_fuel,
                'total_refueled': round(total_refueled, 2),
                'refuel_count': refuel_count,
                'total_drained': round(total_drained, 2),
                'drain_count': drain_count,
                'fuel_consumed': consumed,
                'consumption_rate': rate,
                'fuel_economy': economy,
                'benchmark_rate': benchmark,
                'variance_pct': variance,
                'theft_suspected': theft_flag,
                'efficiency_status': status,
            }

            if rec:
                rec.write(vals)
            else:
                rec = self.create(vals)

            created_records |= rec

        return created_records
