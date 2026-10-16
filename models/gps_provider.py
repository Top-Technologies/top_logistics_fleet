from datetime import datetime, timedelta
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..integration.gps_client import get_gps_client

_logger = logging.getLogger(__name__)


class GPSProvider(models.Model):
    _name = 'top.gps.provider'
    _description = 'GPS Provider API Configuration'
    _order = 'name'

    name = fields.Char(string='Provider Name', required=True)
    api_url = fields.Char(string='API URL', required=True)
    api_key = fields.Char(string='API Key / Token')
    username = fields.Char(string='Username')
    password = fields.Char(string='Password / Secret')
    auth_type = fields.Selection([
        ('token', 'API Token'),
        ('bearer', 'Bearer Token'),
        ('basic', 'Basic Auth'),
        ('api_key', 'API Key Header'),
    ], string='Authentication Type', default='token', required=True)

    polling_interval = fields.Integer(string='Polling Interval (Minutes)', default=5)
    active = fields.Boolean(string='Active', default=True)
    timeout = fields.Integer(string='Timeout (Seconds)', default=30)
    last_sync = fields.Datetime(string='Last Synchronized', readonly=True)
    sync_status = fields.Selection([
        ('not_synced', 'Not Synced'),
        ('running', 'Syncing...'),
        ('success', 'Successful'),
        ('failed', 'Failed'),
    ], string='Sync Status', default='not_synced', readonly=True)

    # Section 46: GPS Error Handling fields
    error_message = fields.Text(string='Last Error Message', readonly=True)
    retry_count = fields.Integer(string='Consecutive Retry Failures', default=0, readonly=True)
    error_type = fields.Selection([
        ('timeout', 'API Timeout'),
        ('auth_fail', 'Authentication Failure'),
        ('invalid_device', 'Invalid Device / IMEI'),
        ('vehicle_not_found', 'Vehicle Not Found'),
        ('parse_error', 'Data Parsing Error'),
        ('duplicate', 'Duplicate GPS Record'),
        ('unavailable', 'Provider Unavailable'),
        ('other', 'General System Error'),
    ], string='Error Classification', readonly=True)

    # Section 48: GPS Data Retention Policy
    retention_days = fields.Integer(
        string='Position Data Retention (Days)',
        default=60,
        help='Raw high-frequency GPS positions older than this threshold will be purged to maintain database performance.'
    )

    device_ids = fields.One2many('top.gps.device', 'provider_id', string='Linked Devices')
    device_count = fields.Integer(string='Device Count', compute='_compute_device_count')

    @api.depends('device_ids')
    def _compute_device_count(self):
        for rec in self:
            rec.device_count = len(rec.device_ids)

    def action_test_connection(self):
        """Performs live authentication handshake and unit discovery with the GPS provider."""
        self.ensure_one()
        if not self.api_url:
            raise UserError(_("Please provide an API URL before testing the connection."))
        if not self.api_key:
            raise UserError(_("Please provide an API Key / Token before testing the connection."))
        
        try:
            client = get_gps_client(self)
            client.authenticate()
            units = client.get_devices()
            unit_count = len(units)

            self.write({
                'sync_status': 'success',
                'error_message': False,
                'error_type': False,
                'retry_count': 0,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful!'),
                    'message': _('Successfully connected to %s! Discovered %d live units.') % (self.name, unit_count),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            self.write({
                'sync_status': 'failed',
                'error_type': 'auth_fail',
                'error_message': str(e),
                'retry_count': self.retry_count + 1,
            })
            raise UserError(_("Connection failed: %s") % str(e))

    def action_discover_wialon_devices(self):
        """
        Discovers all AVL units from Wialon, registers them in top.gps.device,
        and matches or creates matching fleet.vehicle records.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        client = get_gps_client(self)
        try:
            client.authenticate()
            units = client.get_devices()
        except Exception as e:
            self.write({
                'sync_status': 'failed',
                'error_type': 'auth_fail',
                'error_message': str(e),
            })
            raise UserError(_("Failed to fetch units from Wialon: %s") % str(e))

        # Default model for vehicles if none matched
        default_model = self.env['fleet.vehicle.model'].search([], limit=1)
        if not default_model:
            brand = self.env['fleet.vehicle.model.brand'].search([], limit=1)
            if not brand:
                brand = self.env['fleet.vehicle.model.brand'].create({'name': 'Commercial Fleet'})
            default_model = self.env['fleet.vehicle.model'].create({
                'name': 'Fleet Commercial Truck',
                'brand_id': brand.id,
            })

        Device = self.env['top.gps.device']
        Vehicle = self.env['fleet.vehicle']
        Position = self.env['top.gps.position']

        created_dev_count = 0
        updated_dev_count = 0
        created_veh_count = 0

        for u in units:
            unit_id = str(u['device_id'])
            unit_name = u['name']
            clean_name = unit_name.strip()

            # Find or create GPS Device by unique device_id
            device = Device.search([('device_id', '=', unit_id)], limit=1)
            if not device and u.get('imei'):
                device = Device.search([('imei', '=', u['imei'])], limit=1)

            # Find matching vehicle by plate or name
            vehicle = False
            if device and device.vehicle_id:
                vehicle = device.vehicle_id
            else:
                vehicle = Vehicle.search([
                    '|',
                    ('license_plate', '=ilike', clean_name),
                    ('name', '=ilike', clean_name),
                ], limit=1)
                if not vehicle:
                    norm = clean_name.replace(' ', '').replace('-', '').upper()
                    all_vehicles = Vehicle.search([])
                    for v in all_vehicles:
                        v_norm = (v.license_plate or '').replace(' ', '').replace('-', '').upper()
                        if v_norm and v_norm == norm:
                            vehicle = v
                            break

                if not vehicle:
                    vehicle = Vehicle.create({
                        'name': clean_name,
                        'license_plate': clean_name,
                        'model_id': default_model.id,
                        'operational_status': 'available',
                        'odometer': u['odometer'] or 0.0,
                    })
                    created_veh_count += 1

            vals = {
                'name': clean_name,
                'device_id': unit_id,
                'imei': u['imei'],
                'sim_number': u['sim_number'],
                'provider_id': self.id,
                'provider': 'wialon',
                'vehicle_id': vehicle.id if vehicle else False,
                'latitude': u['latitude'],
                'longitude': u['longitude'],
                'altitude': u['altitude'],
                'speed': u['speed'],
                'direction': u['direction'],
                'gps_signal': u['gps_signal'],
                'ignition': u['ignition'],
                'odometer': u['odometer'],
                'fuel_level': u['fuel_level'],
                'battery': u['battery'],
                'last_communication': u['last_communication'] or now,
                'last_sync': now,
                'status': u['status'],
            }

            if not device:
                device = Device.create(vals)
                created_dev_count += 1
            else:
                device.write(vals)
                updated_dev_count += 1

            if vehicle:
                if not vehicle.gps_device_id:
                    vehicle.write({'gps_device_id': device.id})
                if u['odometer'] and u['odometer'] > (vehicle.odometer or 0.0):
                    vehicle.write({'odometer': u['odometer']})

            # Record initial position telemetry log
            if u['latitude'] and u['longitude']:
                Position.create({
                    'device_id': device.id,
                    'vehicle_id': vehicle.id if vehicle else False,
                    'timestamp': u['last_communication'] or now,
                    'latitude': u['latitude'],
                    'longitude': u['longitude'],
                    'altitude': u['altitude'],
                    'speed': u['speed'],
                    'direction': u['direction'],
                    'ignition': u['ignition'],
                    'odometer': u['odometer'],
                    'fuel_level': u['fuel_level'],
                    'battery': u['battery'],
                    'gps_signal': u['gps_signal'],
                    'engine_status': 'running' if u['ignition'] and u['speed'] > 5.0 else ('idling' if u['ignition'] else 'stopped'),
                })

        self.write({
            'last_sync': now,
            'sync_status': 'success',
            'error_message': False,
            'error_type': False,
            'retry_count': 0,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Wialon Discovery & Sync Complete'),
                'message': _('Successfully synced %d units (%d registered, %d updated, %d vehicles created/linked).') % (
                    len(units), created_dev_count, updated_dev_count, created_veh_count
                ),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_sync_now(self):
        """Triggers manual synchronization for this provider."""
        self.ensure_one()
        return self._sync_provider_telemetry()

    def _sync_provider_telemetry(self):
        """
        Synchronizes GPS device telemetry based on Section 22 & 24 standardization.
        Section 46: Error handling guarantees that failed sync never stops main Odoo.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        self.write({'sync_status': 'running'})

        try:
            client = get_gps_client(self)
            client.authenticate()
            units = client.get_devices()
            units_by_id = {str(u['device_id']): u for u in units}
            units_by_name = {u['name'].strip(): u for u in units}

            Device = self.env['top.gps.device']
            Vehicle = self.env['fleet.vehicle']
            Position = self.env['top.gps.position']

            # Update existing devices linked to this provider
            devices = self.device_ids.filtered(lambda d: d.status != 'suspended')
            for device in devices:
                unit_data = units_by_id.get(str(device.device_id)) or units_by_name.get(device.name.strip())
                if unit_data:
                    old_fuel = device.fuel_level or 0.0
                    new_fuel = float(unit_data.get('fuel_level') or 0.0)
                    if old_fuel > 0.0 and new_fuel > 0.0 and device.vehicle_id:
                        fuel_diff = new_fuel - old_fuel
                        if fuel_diff >= 10.0:
                            self.env['top.gps.fuel.transaction'].create({
                                'transaction_type': 'refuel',
                                'timestamp': unit_data.get('last_communication') or now,
                                'vehicle_id': device.vehicle_id.id,
                                'device_id': device.id,
                                'driver_id': device.vehicle_id.driver_id.id if device.vehicle_id.driver_id else False,
                                'initial_fuel': round(old_fuel, 2),
                                'final_fuel': round(new_fuel, 2),
                                'volume': round(fuel_diff, 2),
                                'odometer': unit_data.get('odometer'),
                                'speed': unit_data.get('speed'),
                                'latitude': unit_data.get('latitude'),
                                'longitude': unit_data.get('longitude'),
                                'state': 'detected',
                            })
                        elif fuel_diff <= -10.0 and float(unit_data.get('speed') or 0.0) <= 10.0:
                            self.env['top.gps.fuel.transaction'].create({
                                'transaction_type': 'drain',
                                'timestamp': unit_data.get('last_communication') or now,
                                'vehicle_id': device.vehicle_id.id,
                                'device_id': device.id,
                                'driver_id': device.vehicle_id.driver_id.id if device.vehicle_id.driver_id else False,
                                'initial_fuel': round(old_fuel, 2),
                                'final_fuel': round(new_fuel, 2),
                                'volume': round(abs(fuel_diff), 2),
                                'odometer': unit_data.get('odometer'),
                                'speed': unit_data.get('speed'),
                                'latitude': unit_data.get('latitude'),
                                'longitude': unit_data.get('longitude'),
                                'state': 'flagged',
                            })

                    device.write({
                        'latitude': unit_data['latitude'],
                        'longitude': unit_data['longitude'],
                        'altitude': unit_data['altitude'],
                        'speed': unit_data['speed'],
                        'direction': unit_data['direction'],
                        'gps_signal': unit_data['gps_signal'],
                        'ignition': unit_data['ignition'],
                        'odometer': unit_data['odometer'],
                        'fuel_level': unit_data['fuel_level'],
                        'battery': unit_data['battery'],
                        'last_communication': unit_data['last_communication'] or now,
                        'last_sync': now,
                        'status': unit_data['status'],
                    })

                if not device.device_id and not device.imei:
                    _logger.warning("GPS Device %s has no valid ID or IMEI.", device.name)
                    continue

                if device.vehicle_id:
                    v = device.vehicle_id
                    if device.odometer and device.odometer > (v.odometer or 0.0):
                        v.write({'odometer': device.odometer})
                    
                    # Check active trip for this vehicle (Section 26)
                    active_trip = self.env['top.fleet.trip'].search([
                        ('vehicle_id', '=', v.id),
                        ('state', '=', 'in_transit'),
                    ], limit=1)

                    # Step 7: Record position log during active trip or operational shift (Section 21)
                    if device.latitude and device.longitude:
                        Position.create({
                            'device_id': device.id,
                            'vehicle_id': v.id,
                            'trip_id': active_trip.id if active_trip else False,
                            'timestamp': device.last_communication or now,
                            'latitude': device.latitude,
                            'longitude': device.longitude,
                            'altitude': device.altitude,
                            'speed': device.speed,
                            'direction': device.direction,
                            'ignition': device.ignition,
                            'odometer': device.odometer,
                            'fuel_level': device.fuel_level,
                            'battery': device.battery,
                            'gps_signal': device.gps_signal,
                            'engine_status': 'running' if device.ignition and (device.speed or 0) > 5.0 else ('idling' if device.ignition else 'stopped'),
                        })

                    # Step 8: Update trip distance & telemetry if on active trip
                    if active_trip:
                        trip_vals = {}
                        if active_trip.start_odometer and device.odometer:
                            trip_vals['actual_distance'] = max(0.0, device.odometer - active_trip.start_odometer)
                        if not active_trip.start_fuel and device.fuel_level:
                            trip_vals['start_fuel'] = device.fuel_level
                        if trip_vals:
                            active_trip.write(trip_vals)

                    # Step 9: Evaluate Automatic Safety Alerts & Geofences (Section 53)
                    self._evaluate_telemetry_alerts(device, v, active_trip, now)

            self.write({
                'last_sync': now,
                'sync_status': 'success',
                'error_message': False,
                'error_type': False,
                'retry_count': 0,
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Telemetry Synchronized'),
                    'message': _('Successfully updated live GPS telemetry for %d devices.') % len(devices),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            # Section 46: Record specific error classification and avoid stopping Odoo
            _logger.exception("GPS Sync failed for provider %s: %s", self.name, str(e))
            err_str = str(e).lower()
            err_type = 'other'
            if 'timeout' in err_str:
                err_type = 'timeout'
            elif 'auth' in err_str or 'token' in err_str:
                err_type = 'auth_fail'
            elif 'parse' in err_str or 'json' in err_str:
                err_type = 'parse_error'
            elif 'unavail' in err_str or 'connect' in err_str:
                err_type = 'unavailable'

            self.write({
                'last_sync': now,
                'sync_status': 'failed',
                'error_type': err_type,
                'error_message': str(e),
                'retry_count': self.retry_count + 1,
            })

    def _evaluate_telemetry_alerts(self, device, vehicle, active_trip, now):
        """Evaluates telematics data against safety rules and alerts configured in Section 53."""
        config = self.env['top.fleet.alert.config'].get_active_config()

        # 1. Overspeed Alert (Section 50 & 53)
        if device.speed and config.overspeed_threshold_kmh and device.speed > config.overspeed_threshold_kmh:
            event = self.env['top.gps.event'].create({
                'name': _("Overspeed Alert: %s km/h (Threshold: %s km/h)") % (device.speed, config.overspeed_threshold_kmh),
                'event_type': 'overspeed',
                'severity': 'danger',
                'vehicle_id': vehicle.id,
                'driver_id': active_trip.driver_id.id if active_trip else False,
                'trip_id': active_trip.id if active_trip else False,
                'timestamp': now,
                'latitude': device.latitude,
                'longitude': device.longitude,
                'speed': device.speed,
                'speed_limit': config.overspeed_threshold_kmh,
            })
            if active_trip:
                activity_type = self.env.ref('top_logistics_fleet.mail_act_overspeed', raise_if_not_found=False)
                if activity_type:
                    active_trip.activity_schedule(
                        'top_logistics_fleet.mail_act_overspeed',
                        summary=_("Overspeed Alert: %s km/h on trip %s") % (device.speed, active_trip.name),
                        user_id=active_trip.trip_coordinator_id.id if active_trip.trip_coordinator_id else self.env.user.id,
                    )
            template = self.env.ref('top_logistics_fleet.mail_template_overspeed_detected', raise_if_not_found=False)
            if template:
                template.send_mail(event.id, force_send=False)

        # 2. Movement Outside Working Hours / Unauthorized Movement (Section 53)
        if config.alert_on_unauthorized_movement and (device.ignition or (device.speed and device.speed > 5.0)):
            hour = now.hour
            is_night = hour >= 20 or hour < 6
            if not active_trip or is_night:
                self.env['top.gps.event'].create({
                    'name': _("Unauthorized Movement / Outside Hours Detected (%s km/h)") % (device.speed or 0),
                    'event_type': 'unauthorized_movement',
                    'severity': 'warning',
                    'vehicle_id': vehicle.id,
                    'trip_id': active_trip.id if active_trip else False,
                    'timestamp': now,
                    'latitude': device.latitude,
                    'longitude': device.longitude,
                    'speed': device.speed,
                    'notes': _("Vehicle motion recorded outside authorized working hours (20:00-06:00) or without active trip assignment."),
                })

        # 3. Geofence Evaluation (Section 27 & 53)
        if config.alert_on_geofence and device.latitude and device.longitude:
            geofences = self.env['top.gps.geofence'].search([('active', '=', True)])
            for gf in geofences:
                d_lat = (device.latitude - gf.latitude) * 111000.0
                d_lng = (device.longitude - gf.longitude) * 111000.0 * 0.98
                dist_m = (d_lat**2 + d_lng**2)**0.5
                if dist_m <= (gf.radius or 200.0):
                    if gf.category == 'restricted':
                        self.env['top.gps.event'].create({
                            'name': _("Restricted Geofence Breach: Entered %s") % gf.name,
                            'event_type': 'geofence_entry',
                            'severity': 'danger',
                            'vehicle_id': vehicle.id,
                            'trip_id': active_trip.id if active_trip else False,
                            'geofence_id': gf.id,
                            'timestamp': now,
                            'latitude': device.latitude,
                            'longitude': device.longitude,
                            'speed': device.speed,
                        })

    def action_purge_old_positions(self):
        """Section 48: Purges raw historical positions older than retention days."""
        self.ensure_one()
        days = self.retention_days or 60
        threshold_date = fields.Datetime.now() - timedelta(days=days)
        # Purge positions that are NOT linked to open/active trips
        old_positions = self.env['top.gps.position'].search([
            ('device_id', 'in', self.device_ids.ids),
            ('timestamp', '<', threshold_date),
            ('trip_id.state', '!=', 'in_transit'),
        ])
        count = len(old_positions)
        old_positions.unlink()
        _logger.info("Purged %d historical GPS positions older than %d days for provider %s", count, days, self.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Retention Purge Completed'),
                'message': _('Purged %s historical GPS telemetry positions.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def cron_sync_all_active_providers(self):
        """Cron job to sync telemetry for all active providers (Section 22 & 47)."""
        providers = self.search([('active', '=', True)])
        for p in providers:
            p._sync_provider_telemetry()

    @api.model
    def cron_purge_all_providers_retention(self):
        """Section 48: Scheduled cron job to archive/clean up old telemetry."""
        providers = self.search([('active', '=', True)])
        for p in providers:
            p.action_purge_old_positions()
