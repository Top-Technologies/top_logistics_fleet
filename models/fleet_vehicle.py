from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    operational_status = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('on_trip', 'On Trip'),
        ('maintenance', 'Under Maintenance'),
        ('inactive', 'Inactive'),
    ], string='Operational Status', default='available', tracking=True, index=True)

    # Compliance & Validity (Section 12)
    registration_expiry = fields.Date(string='Registration Expiry Date', tracking=True)
    insurance_expiry = fields.Date(string='Insurance Expiry Date', tracking=True)
    inspection_expiry = fields.Date(string='Inspection Expiry Date', tracking=True)

    # Operational Capacity & Location (Section 10)
    current_location = fields.Char(string='Current Location', default='Main Depot')
    capacity_passengers = fields.Integer(string='Passenger Capacity', default=4)
    capacity_cargo_kg = fields.Float(string='Cargo Capacity (kg)', default=500.0)

    # GPS Linkage (Sections 20 & 25)
    gps_device_id = fields.Many2one(
        'top.gps.device',
        string='GPS Tracking Device',
        tracking=True,
    )
    live_speed = fields.Float(related='gps_device_id.speed', string='Live Speed (km/h)', readonly=True)
    live_odometer = fields.Float(related='gps_device_id.odometer', string='Live Odometer (km)', readonly=True)
    live_ignition = fields.Boolean(related='gps_device_id.ignition', string='Live Ignition', readonly=True)
    live_last_communication = fields.Datetime(related='gps_device_id.last_communication', string='Last GPS Ping', readonly=True)
    live_latitude = fields.Float(related='gps_device_id.latitude', string='Latitude', digits=(10, 6), readonly=True)
    live_longitude = fields.Float(related='gps_device_id.longitude', string='Longitude', digits=(10, 6), readonly=True)
    live_altitude = fields.Float(related='gps_device_id.altitude', string='Altitude (m)', readonly=True)
    live_fuel_level = fields.Float(related='gps_device_id.fuel_level', string='Live Fuel (L)', readonly=True)
    live_battery = fields.Float(related='gps_device_id.battery', string='Battery Voltage (V)', readonly=True)
    live_gps_signal = fields.Integer(related='gps_device_id.gps_signal', string='GPS Satellites', readonly=True)
    live_address = fields.Char(related='gps_device_id.address', string='Live Address', readonly=True)

    has_document_expired = fields.Boolean(
        string='Has Expired Documents',
        compute='_compute_document_compliance',
        store=True,
    )
    document_compliance_status = fields.Char(
        string='Document Compliance',
        compute='_compute_document_compliance',
        store=True,
    )

    # Section 54: Vehicle Cost Analysis & Utilization KPIs
    expected_fuel_consumption = fields.Float(
        string='Expected Consumption (L/100km)',
        default=12.0,
        help='Target benchmark fuel consumption rate in Litres per 100 km.'
    )
    fuel_log_ids = fields.One2many('top.fleet.fuel.log', 'vehicle_id', string='Fuel Logs')
    gps_fuel_transaction_ids = fields.One2many('top.gps.fuel.transaction', 'vehicle_id', string='GPS Fuel Transactions')
    fuel_analysis_ids = fields.One2many('top.fleet.fuel.analysis', 'vehicle_id', string='Fuel Analyses')
    trip_ids = fields.One2many('top.fleet.trip', 'vehicle_id', string='Trips')
    total_trips_count = fields.Integer(string='Completed Trips Count', compute='_compute_vehicle_operating_costs', store=True)
    total_fuel_litres = fields.Float(string='Total Fuel (L)', compute='_compute_vehicle_operating_costs', store=True)
    total_fuel_cost = fields.Float(string='Total Fuel Cost', compute='_compute_vehicle_operating_costs', store=True)
    total_operating_cost = fields.Float(string='Total Vehicle Operating Cost', compute='_compute_vehicle_operating_costs', store=True)
    
    # Section 54 Formulas:
    # 1. Cost per KM = Total Vehicle Operating Cost ÷ Actual Distance
    cost_per_km = fields.Float(string='Cost / KM (Total Op Cost ÷ Distance)', compute='_compute_vehicle_operating_costs', store=True)
    # 2. Fuel Cost per KM = Fuel Cost ÷ Distance
    fuel_cost_per_km = fields.Float(string='Fuel Cost / KM (Fuel Cost ÷ Distance)', compute='_compute_vehicle_operating_costs', store=True)
    # 3. Cost per Trip = Trip Related Cost ÷ Trip
    cost_per_trip = fields.Float(string='Cost / Trip (Op Cost ÷ Trips)', compute='_compute_vehicle_operating_costs', store=True)
    # 4. Vehicle Utilization = Assigned Hours ÷ Available Hours × 100
    available_hours = fields.Float(string='Available Operational Hours / Month', default=240.0)
    assigned_hours = fields.Float(string='Assigned Hours', compute='_compute_vehicle_operating_costs', store=True)
    utilization_rate = fields.Float(string='Vehicle Utilization (%)', compute='_compute_vehicle_operating_costs', store=True)

    # Maintenance Service Schedule (Section 33)
    service_interval_km = fields.Float(string='Service Interval (km)', default=5000.0)
    last_service_odometer = fields.Float(string='Last Service Odometer (km)', default=0.0)
    next_service_odometer = fields.Float(
        string='Next Service Due at (km)',
        compute='_compute_service_due',
        store=True
    )
    is_service_due = fields.Boolean(
        string='Maintenance Service Due',
        compute='_compute_service_due',
        store=True
    )
    service_status = fields.Selection([
        ('due', 'Service Due'),
        ('ok', 'Up to Date'),
    ], string='Service Status', compute='_compute_service_due', store=True)

    @api.depends('odometer', 'last_service_odometer', 'service_interval_km')
    def _compute_service_due(self):
        for v in self:
            v.next_service_odometer = (v.last_service_odometer or 0.0) + (v.service_interval_km or 5000.0)
            if (v.odometer or 0.0) >= v.next_service_odometer:
                v.is_service_due = True
                v.service_status = 'due'
            else:
                v.is_service_due = False
                v.service_status = 'ok'

    @api.depends('fuel_log_ids.quantity', 'fuel_log_ids.total_cost', 'odometer', 'trip_ids.actual_duration', 'trip_ids.actual_distance', 'available_hours')
    def _compute_vehicle_operating_costs(self):
        for v in self:
            total_litres = sum(v.fuel_log_ids.mapped('quantity'))
            total_fuel = sum(v.fuel_log_ids.mapped('total_cost'))
            v.total_fuel_litres = total_litres
            v.total_fuel_cost = total_fuel

            # Accident repair costs
            accidents = self.env['top.fleet.accident'].search([('vehicle_id', '=', v.id), ('state', '!=', 'cancelled')])
            accident_costs = sum(accidents.mapped('actual_cost')) or sum(accidents.mapped('estimated_cost'))
            total_operating = total_fuel + accident_costs
            v.total_operating_cost = total_operating

            completed_trips = v.trip_ids.filtered(lambda t: t.state in ['completed', 'reconciled', 'closed'])
            v.total_trips_count = len(completed_trips)
            total_assigned_hrs = sum(completed_trips.mapped('actual_duration'))
            v.assigned_hours = total_assigned_hrs

            # Section 54 Formula 4: Vehicle Utilization = Assigned Hours / Available Hours * 100
            avail = v.available_hours or 240.0
            v.utilization_rate = round((total_assigned_hrs / avail) * 100.0, 2) if avail > 0 else 0.0

            # Actual Distance (from trips or vehicle odometer)
            actual_dist = sum(completed_trips.mapped('actual_distance')) or (v.odometer or 0.0)

            # Section 54 Formula 1: Cost per KM = Total Vehicle Operating Cost / Actual Distance
            if actual_dist > 0:
                v.cost_per_km = round(total_operating / actual_dist, 2)
                # Section 54 Formula 2: Fuel Cost per KM = Fuel Cost / Distance
                v.fuel_cost_per_km = round(total_fuel / actual_dist, 2)
            else:
                v.cost_per_km = 0.0
                v.fuel_cost_per_km = 0.0

            # Section 54 Formula 3: Cost per Trip = Trip Related Cost / Trip
            if v.total_trips_count > 0:
                v.cost_per_trip = round(total_operating / v.total_trips_count, 2)
            else:
                v.cost_per_trip = 0.0

    @api.depends('registration_expiry', 'insurance_expiry', 'inspection_expiry')
    def _compute_document_compliance(self):
        today = fields.Date.today()
        for vehicle in self:
            expired = []
            if vehicle.registration_expiry and vehicle.registration_expiry < today:
                expired.append(_('Registration'))
            if vehicle.insurance_expiry and vehicle.insurance_expiry < today:
                expired.append(_('Insurance'))
            if vehicle.inspection_expiry and vehicle.inspection_expiry < today:
                expired.append(_('Inspection'))

            if expired:
                vehicle.has_document_expired = True
                vehicle.document_compliance_status = _("Expired: %s") % ", ".join(expired)
            else:
                vehicle.has_document_expired = False
                vehicle.document_compliance_status = _("Valid & Compliant")

    def action_view_on_map(self):
        """Opens live vehicle location according to configured map provider (Sections 25 & 52)."""
        self.ensure_one()
        lat = self.live_latitude or (self.gps_device_id and self.gps_device_id.latitude)
        lng = self.live_longitude or (self.gps_device_id and self.gps_device_id.longitude)
        if not lat or not lng:
            raise ValidationError(_("No GPS coordinates recorded for vehicle %s.") % self.name)

        config = self.env['top.fleet.alert.config'].get_active_config()
        if config.mapping_provider == 'osm':
            url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=16/{lat}/{lng}"
        else:
            url = f"https://www.google.com/maps?q={lat},{lng}"

        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def trigger_service_maintenance_request(self):
        """Automatically triggers a maintenance service ticket when service interval is reached (Section 33 & 50)."""
        self.ensure_one()
        maintenance_model = self.env.get('maintenance.request')
        if maintenance_model:
            vals = {
                'name': _("Scheduled Service Due (%s km) - %s") % (int(self.next_service_odometer), self.name),
                'maintenance_type': 'preventive',
                'description': _("Vehicle has reached scheduled service interval.\nCurrent Odometer: %s km\nDue Odometer: %s km") % (
                    self.odometer, self.next_service_odometer
                ),
            }
            req = maintenance_model.sudo().create(vals)
            self.message_post(
                body=_("Preventive service interval reached (%s km). Automated Maintenance Request created: #%s") % (
                    int(self.odometer), req.id
                )
            )

    @api.model
    def cron_check_compliance_and_alerts(self):
        """Section 50 & 53: Daily scan for vehicle document expiries and maintenance alerts."""
        today = fields.Date.today()
        warning_window = today + timedelta(days=30)
        vehicles = self.search([('active', '=', True)])
        officer_group = self.env.ref('top_logistics_fleet.group_fleet_officer', raise_if_not_found=False)
        officer_user = officer_group.users[0] if officer_group and officer_group.users else self.env.user

        for v in vehicles:
            # Check maintenance due
            if v.is_service_due:
                v.activity_schedule(
                    'top_logistics_fleet.mail_act_maintenance_due',
                    summary=_("Service Due for %s") % v.name,
                    user_id=officer_user.id,
                )
            # Check document expiries
            if v.insurance_expiry and v.insurance_expiry <= warning_window:
                v.activity_schedule(
                    'top_logistics_fleet.mail_act_doc_expiring',
                    summary=_("Insurance Expiring Soon for %s (%s)") % (v.name, v.insurance_expiry),
                    user_id=officer_user.id,
                )

    def check_availability(self, start_date, end_date, exclude_trip_id=None):
        """Validates if vehicle is operational, not in maintenance, not expired, and free of overlapping trips."""
        self.ensure_one()
        today = fields.Date.today()

        if not self.active or self.operational_status in ['maintenance', 'inactive']:
            return False, _("Vehicle %s is currently inactive or under maintenance.") % self.name

        if self.registration_expiry and self.registration_expiry < today:
            return False, _("Vehicle %s registration expired on %s.") % (self.name, self.registration_expiry)
        if self.insurance_expiry and self.insurance_expiry < today:
            return False, _("Vehicle %s insurance expired on %s.") % (self.name, self.insurance_expiry)
        if self.inspection_expiry and self.inspection_expiry < today:
            return False, _("Vehicle %s inspection expired on %s.") % (self.name, self.inspection_expiry)

        domain = [
            ('vehicle_id', '=', self.id),
            ('state', 'in', ['ready', 'dispatched', 'in_transit']),
            ('planned_departure', '<', end_date),
            ('planned_arrival', '>', start_date),
        ]
        if exclude_trip_id:
            domain.append(('id', '!=', exclude_trip_id))

        overlapping = self.env['top.fleet.trip'].search(domain, limit=1)
        if overlapping:
            return False, _("Vehicle %s is already assigned to trip %s during this time window.") % (
                self.name, overlapping.name
            )

        return True, _("Available")

    def action_view_fuel_analytics(self):
        self.ensure_one()
        return {
            'name': _('Fuel Analytics: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'top.fleet.fuel.analysis',
            'view_mode': 'pivot,graph,list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    def action_view_gps_fuel_transactions(self):
        self.ensure_one()
        return {
            'name': _('GPS Fuel Events: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'top.gps.fuel.transaction',
            'view_mode': 'list,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

