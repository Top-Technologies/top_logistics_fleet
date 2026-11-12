from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class FleetTrip(models.Model):
    _name = 'top.fleet.trip'
    _description = 'Fleet Trip Execution'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'planned_departure desc, id desc'

    name = fields.Char(
        string='Trip Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
    )
    request_id = fields.Many2one(
        'top.transport.request',
        string='Transport Request',
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    request_ids = fields.Many2many(
        'top.transport.request',
        'top_trip_request_rel',
        'trip_id',
        'request_id',
        string='Consolidated Transport Requests',
        help='Multiple transport requests served together in this consolidated transport order.',
    )
    fleet_order_type_id = fields.Many2one(
        'approval.request',
        string='Fleet Order Type',
        tracking=True,
        help="Approval request from the Approvals module representing this fleet order approval subject.",
    )
    inspection_id = fields.Many2one(
        'top.fleet.vehicle.inspection',
        string='Pre-Trip Vehicle Inspection',
        tracking=True,
        help='Technical condition inspection record conducted prior to dispatch.',
    )
    trip_type_id = fields.Many2one(
        'top.transport.request.type',
        string='Trip Type',
        tracking=True,
        help="Trip type classification from transport request.",
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        tracking=True,
        index=True,
    )
    vehicle_last_service_date = fields.Date(
        related='vehicle_id.last_service_date',
        string='Vehicle Last Service Date',
        readonly=True,
    )
    vehicle_next_service_date = fields.Date(
        related='vehicle_id.next_service_date',
        string='Vehicle Next Service Due',
        readonly=True,
    )
    vehicle_service_status = fields.Selection(
        related='vehicle_id.service_status',
        string='Vehicle Service Status',
        readonly=True,
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='Assigned Driver',
        required=True,
        domain="[('is_driver', '=', True)]",
        tracking=True,
        index=True,
    )
    driver_license_expiry_date = fields.Date(
        related='driver_id.license_expiry_date',
        string='Driver License Expiration',
        readonly=True,
    )
    driver_is_license_expired = fields.Boolean(
        related='driver_id.is_license_expired',
        string='Driver License Expired',
        readonly=True,
    )
    driver_license_compliance = fields.Char(
        related='driver_id.license_compliance_status',
        string='Driver License Status',
        readonly=True,
    )
    backup_driver_id = fields.Many2one(
        'hr.employee',
        string='Backup Driver',
        domain="[('is_driver', '=', True)]",
    )
    trip_coordinator_id = fields.Many2one(
        'res.users',
        string='Trip Coordinator',
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    # Route & Schedule
    origin_location_id = fields.Many2one(
        'top.logistics.location',
        string='Origin Location',
        tracking=True,
    )
    destination_location_id = fields.Many2one(
        'top.logistics.location',
        string='Destination Location',
        tracking=True,
    )
    origin = fields.Char(string='Origin', required=True)
    destination = fields.Char(string='Destination', required=True)
    waypoint_ids = fields.One2many(
        'top.fleet.trip.waypoint',
        'trip_id',
        string='Waypoints / Stops',
    )
    total_stops_count = fields.Integer(
        string='Total Stops Planned',
        compute='_compute_stop_metrics',
        store=True,
    )
    completed_stops_count = fields.Integer(
        string='Stops Completed',
        compute='_compute_stop_metrics',
        store=True,
    )
    cancelled_stops_count = fields.Integer(
        string='Stops Cancelled',
        compute='_compute_stop_metrics',
        store=True,
    )
    pending_stops_count = fields.Integer(
        string='Stops Pending',
        compute='_compute_stop_metrics',
        store=True,
    )
    planned_departure = fields.Datetime(string='Planned Departure', required=True, tracking=True)
    planned_arrival = fields.Datetime(string='Planned Arrival', required=True, tracking=True)
    actual_departure = fields.Datetime(string='Actual Departure', tracking=True)
    actual_arrival = fields.Datetime(string='Actual Arrival', tracking=True)
    purpose = fields.Text(string='Trip Purpose')
    special_instructions = fields.Text(string='Special Instructions / Notes')

    # Distance & Duration Metrics
    planned_distance = fields.Float(string='Planned Distance (km)')
    actual_distance = fields.Float(string='Actual Distance (km)', compute='_compute_actual_distance', store=True, readonly=False, tracking=True)
    planned_duration = fields.Float(string='Planned Duration (Hours)')
    actual_duration = fields.Float(string='Actual Duration (Hours)', compute='_compute_actual_duration', store=True)

    # Cargo & Freight Details
    cargo_required = fields.Boolean(string='Cargo Required', default=False, tracking=True)
    cargo_load_type = fields.Selection(
        [
            ('full', 'Full Load (ሙሉ ጭነት)'),
            ('empty', 'Empty Load (ባዶ ጭነት)'),
        ],
        string='Load Type',
        default='full',
        tracking=True,
    )
    cargo_product_id = fields.Many2one('product.product', string='Loading Type / Product', tracking=True)
    cargo_loading_type_desc = fields.Char(string='Product / Commodity Description', tracking=True)
    cargo_location_description = fields.Text(string='Location Description', tracking=True)
    cargo_approver_id = fields.Many2one('res.users', string='Cargo Approver', tracking=True)
    cargo_amount_qty = fields.Float(string='Amount In Quintal', digits='Product Unit of Measure', default=0.0, tracking=True)
    cargo_uom_id = fields.Many2one('uom.uom', string='Amount Unit of Measure', tracking=True)
    cargo_tariff_unit_price = fields.Float(string='Tariff (Unit Price) / Quintal', digits='Product Price', default=0.0, tracking=True)
    cargo_currency_id = fields.Many2one('res.currency', string='Tariff Currency', default=lambda self: self.env.company.currency_id)
    cargo_total_tariff = fields.Monetary(string='Total Tariff Amount', currency_field='cargo_currency_id', compute='_compute_cargo_total_tariff', store=True)
    cargo_load_capacity = fields.Float(string='Load Capacity', digits='Product Unit of Measure', default=0.0, tracking=True)
    cargo_capacity_uom_id = fields.Many2one('uom.uom', string='Capacity UoM', tracking=True)
    cargo_description = fields.Text(string='Cargo / Handling Notes')
    actual_duration_display = fields.Char(string='Time Taken Display', compute='_compute_actual_duration_display')

    # Fuel & Operating Costs
    expected_fuel = fields.Float(string='Planned Fuel (L)', compute='_compute_expected_fuel', store=True, readonly=False, help='Estimated fuel required for planned distance.')
    fuel_log_ids = fields.One2many('top.fleet.fuel.log', 'trip_id', string='Fuel Logs')
    total_refueled = fields.Float(string='Total Refueled (L)', compute='_compute_fuel_metrics', store=True, help='Total litres purchased and added to tank during this trip from fuel logs.')
    fuel_consumed_gps = fields.Float(string='GPS Fuel Consumed (L)', compute='_compute_fuel_metrics', store=True, help='Fuel consumed measured by GPS tank drop plus refuels: (Start Fuel + Refueled) - End/Current Fuel.')
    fuel_consumed_norm = fields.Float(string='Benchmark Norm Fuel (L)', compute='_compute_fuel_metrics', store=True, help='Estimated consumption using vehicle standard rate: (Actual Distance * Benchmark Rate) / 100.')
    fuel_consumption_method = fields.Selection([
        ('gps', 'GPS Sensor Telemetry'),
        ('norm', 'Benchmark Consumption Norm'),
        ('refuel', 'Refueling Purchases'),
    ], string='Fuel Measurement Method', compute='_compute_fuel_metrics', store=True)
    actual_fuel = fields.Float(string='Actual Fuel Consumed (L)', compute='_compute_fuel_metrics', store=True, tracking=True)
    total_fuel_cost = fields.Float(string='Purchased Fuel Cost', compute='_compute_fuel_metrics', store=True)
    consumed_fuel_cost = fields.Float(string='Consumed Fuel Value', compute='_compute_fuel_metrics', store=True)
    fuel_theft_suspected = fields.Boolean(string='Abnormal Fuel Drain / Potential Leak', compute='_compute_fuel_metrics', store=True)
    total_trip_cost = fields.Float(string='Total Trip Cost', compute='_compute_trip_costs', store=True)
    cost_per_km = fields.Float(string='Trip Cost / KM', compute='_compute_trip_costs', store=True)
    fuel_consumption_rate = fields.Float(string='Fuel Rate (L/100km)', compute='_compute_trip_costs', store=True)

    # Reconciliation Variances
    variance_distance = fields.Float(string='Distance Variance (km)', compute='_compute_variances', store=True)
    variance_duration = fields.Float(string='Duration Variance (Hours)', compute='_compute_variances', store=True)
    variance_fuel = fields.Float(string='Fuel Variance (L)', compute='_compute_variances', store=True)

    # GPS Telemetry & Tracking
    gps_device_id = fields.Many2one(
        'top.gps.device',
        string='GPS Device',
        compute='_compute_gps_device',
        store=True,
    )
    gps_status = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('no_device', 'No Device Attached'),
    ], string='GPS Status', compute='_compute_gps_status', store=True)

    current_latitude = fields.Float(related='gps_device_id.latitude', string='Live Latitude', readonly=True)
    current_longitude = fields.Float(related='gps_device_id.longitude', string='Live Longitude', readonly=True)
    current_speed = fields.Float(related='gps_device_id.speed', string='Live Speed (km/h)', readonly=True)
    current_odometer = fields.Float(related='gps_device_id.odometer', string='Live GPS Odometer', readonly=True)
    current_address = fields.Char(related='gps_device_id.address', string='Current Location', readonly=True)
    current_fuel = fields.Float(
        string='Current Fuel (L)',
        compute='_compute_current_fuel',
        readonly=True,
        help='Current live fuel level from vehicle GPS tracker.',
    )

    event_ids = fields.One2many('top.gps.event', 'trip_id', string='GPS Events / Alerts')
    position_ids = fields.One2many('top.gps.position', 'trip_id', string='Trip Track Points')

    # Pre-Dispatch Vehicle Condition Checklist
    chk_tires = fields.Boolean(string='Tires Condition & Pressure Checked', default=True)
    chk_engine = fields.Boolean(string='Engine Sound & Operation Checked', default=True)
    chk_oil = fields.Boolean(string='Engine Oil Level Checked', default=True)
    chk_coolant = fields.Boolean(string='Coolant & Radiator Level Checked', default=True)
    chk_brakes = fields.Boolean(string='Foot & Hand Brakes Tested', default=True)
    chk_lights = fields.Boolean(string='Headlights, Indicators & Brake Lights Checked', default=True)
    chk_spare_tire = fields.Boolean(string='Spare Tire Present & Inflated', default=True)
    chk_tools = fields.Boolean(string='Vehicle Jack & Tools Present', default=True)
    chk_fire_extinguisher = fields.Boolean(string='Fire Extinguisher Valid & Present', default=True)
    chk_first_aid = fields.Boolean(string='First Aid Kit Present', default=True)
    chk_body_condition = fields.Boolean(string='Body Condition Inspected (No Unrecorded Dents)', default=True)

    # General Pre-Dispatch confirmations
    chk_vehicle_inspected = fields.Boolean(string='Vehicle Inspection Confirmed')
    chk_fuel_checked = fields.Boolean(string='Fuel Level Checked')
    chk_driver_confirmed = fields.Boolean(string='Driver Briefed & Confirmed')
    chk_gps_online = fields.Boolean(string='GPS Tracker Online & Active')
    chk_documents_valid = fields.Boolean(string='Vehicle & Driver Documents Physically Checked')
    chk_emergency_equipment = fields.Boolean(string='Emergency Kit & Fire Extinguisher Present')
    start_odometer = fields.Float(string='Starting Odometer (km)')
    start_fuel = fields.Float(string='Starting Fuel Level (L)', tracking=True, help='Initial fuel in vehicle tank in Litres when dispatched.')
    start_fuel_level = fields.Selection([
        ('quarter', '1/4 Tank'),
        ('half', '1/2 Tank'),
        ('three_quarter', '3/4 Tank'),
        ('full', 'Full Tank'),
    ], string='Starting Fuel Level')
    dispatched_by_id = fields.Many2one('res.users', string='Dispatched By', readonly=True)
    dispatch_date = fields.Datetime(string='Dispatch Timestamp', readonly=True)

    # Post-Trip Return Checklist
    vehicle_returned = fields.Boolean(string='Vehicle Returned to Depot', readonly=True)
    end_odometer = fields.Float(string='Ending Odometer (km)', readonly=True)
    end_fuel = fields.Float(string='Ending Fuel Level (L)', tracking=True, readonly=True, help='Final fuel in vehicle tank in Litres upon return inspection.')
    end_fuel_level = fields.Selection([
        ('quarter', '1/4 Tank'),
        ('half', '1/2 Tank'),
        ('three_quarter', '3/4 Tank'),
        ('full', 'Full Tank'),
    ], string='Ending Fuel Gauge', readonly=True)
    return_cleanliness = fields.Selection([
        ('clean', 'Clean / Satisfactory'),
        ('acceptable', 'Normal Dust / Acceptable'),
        ('needs_wash', 'Dirty / Requires Wash'),
    ], string='Cleanliness Status', readonly=True)
    has_damage = fields.Boolean(string='New Damage Flagged', readonly=True)
    damage_description = fields.Text(string='Observed Return Damage', readonly=True)
    missing_equipment = fields.Char(string='Missing Equipment / Tools', readonly=True)
    new_defects = fields.Text(string='New Defects Reported', readonly=True)
    driver_comments = fields.Text(string='Driver Debrief Notes', readonly=True)
    accident_id = fields.Many2one('top.fleet.accident', string='Incident Record', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready / Assigned'),
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('reconciled', 'Reconciled'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Trip Status', default='draft', readonly=True, tracking=True, index=True, copy=False)

    @api.onchange('origin_location_id')
    def _onchange_origin_location_id(self):
        if self.origin_location_id:
            self.origin = self.origin_location_id.display_name or self.origin_location_id.name

    @api.onchange('destination_location_id')
    def _onchange_destination_location_id(self):
        if self.destination_location_id:
            self.destination = self.destination_location_id.display_name or self.destination_location_id.name

    @api.depends('waypoint_ids.state', 'waypoint_ids.completed')
    def _compute_stop_metrics(self):
        for trip in self:
            trip.total_stops_count = len(trip.waypoint_ids)
            trip.completed_stops_count = len(trip.waypoint_ids.filtered(lambda w: w.state == 'completed' or w.completed))
            trip.cancelled_stops_count = len(trip.waypoint_ids.filtered(lambda w: w.state == 'cancelled'))
            trip.pending_stops_count = len(trip.waypoint_ids.filtered(lambda w: w.state == 'pending' and not w.completed))

    @api.depends('actual_duration')
    def _compute_actual_duration_display(self):
        for trip in self:
            if trip.actual_duration:
                total_hours = trip.actual_duration
                hrs = int(total_hours)
                mins = int(round((total_hours - hrs) * 60))
                trip.actual_duration_display = f"{hrs}h {mins}m"
            else:
                trip.actual_duration_display = _("0h 0m")

    @api.depends('start_odometer', 'end_odometer')
    def _compute_actual_distance(self):
        for trip in self:
            if trip.end_odometer and trip.start_odometer and trip.end_odometer >= trip.start_odometer:
                trip.actual_distance = round(trip.end_odometer - trip.start_odometer, 2)
            elif not trip.actual_distance:
                trip.actual_distance = 0.0

    @api.depends('planned_distance', 'vehicle_id.expected_fuel_consumption')
    def _compute_expected_fuel(self):
        for trip in self:
            rate = trip.vehicle_id.expected_fuel_consumption or 12.0
            if trip.planned_distance:
                trip.expected_fuel = round((trip.planned_distance * rate) / 100.0, 2)
            elif not trip.expected_fuel:
                trip.expected_fuel = 0.0

    @api.depends(
        'fuel_log_ids.quantity', 'fuel_log_ids.total_cost',
        'start_fuel', 'end_fuel', 'vehicle_id.live_fuel_level',
        'actual_distance', 'state', 'vehicle_id.expected_fuel_consumption',
        'start_odometer', 'end_odometer', 'planned_distance'
    )
    def _compute_fuel_metrics(self):
        recent_log = self.env['top.fleet.fuel.log'].search([], order='date desc, id desc', limit=1)
        fallback_price = recent_log.unit_price if (recent_log and recent_log.unit_price) else 100.0

        for trip in self:
            refueled = sum(trip.fuel_log_ids.mapped('quantity'))
            refuel_cost = sum(trip.fuel_log_ids.mapped('total_cost'))
            trip.total_refueled = round(refueled, 2)
            trip.total_fuel_cost = round(refuel_cost, 2)

            # Determine distance (actual or odo diff or planned)
            dist = trip.actual_distance or (trip.end_odometer - trip.start_odometer if (trip.end_odometer and trip.start_odometer and trip.end_odometer > trip.start_odometer) else 0.0) or trip.planned_distance or 0.0

            # Determine start fuel
            start_f = trip.start_fuel or 0.0
            if start_f <= 0.0 and trip.vehicle_id.live_fuel_level:
                start_f = trip.vehicle_id.live_fuel_level

            # Determine current/terminal fuel level in tank
            if trip.state in ['completed', 'reconciled', 'closed']:
                terminal_fuel = trip.end_fuel if (trip.end_fuel and trip.end_fuel > 0.0) else (trip.vehicle_id.live_fuel_level or 0.0)
            elif trip.state in ['dispatched', 'in_transit']:
                terminal_fuel = trip.vehicle_id.live_fuel_level or (trip.gps_device_id.fuel_level if trip.gps_device_id else 0.0) or 0.0
            else:
                terminal_fuel = start_f

            # 1. GPS Consumption: (start_fuel + refueled) - terminal_fuel
            if start_f > 0.0 and terminal_fuel > 0.0 and (start_f + refueled) >= terminal_fuel:
                gps_consumed = max(0.0, (start_f + refueled) - terminal_fuel)
            else:
                gps_consumed = 0.0
            trip.fuel_consumed_gps = round(gps_consumed, 2)

            # 2. Benchmark Norm Consumption: (actual_distance * expected_rate) / 100
            rate = trip.vehicle_id.expected_fuel_consumption or 12.0
            norm_consumed = round((dist * rate) / 100.0, 2) if dist > 0.0 else 0.0
            trip.fuel_consumed_norm = norm_consumed

            # 3. Choose primary actual fuel consumed
            if gps_consumed > 0.0:
                trip.actual_fuel = round(gps_consumed, 2)
                trip.fuel_consumption_method = 'gps'
            elif norm_consumed > 0.0:
                trip.actual_fuel = round(norm_consumed, 2)
                trip.fuel_consumption_method = 'norm'
            elif refueled > 0.0:
                trip.actual_fuel = round(refueled, 2)
                trip.fuel_consumption_method = 'refuel'
            else:
                trip.actual_fuel = 0.0
                trip.fuel_consumption_method = 'gps' if (start_f > 0 and terminal_fuel > 0) else 'norm'

            # 4. Monetary value of consumed fuel
            unit_price = (refuel_cost / refueled) if refueled > 0.0 else fallback_price
            trip.consumed_fuel_cost = round(trip.actual_fuel * unit_price, 2)

            # 5. Suspected fuel loss / siphoning alert
            if trip.fuel_consumption_method == 'gps' and norm_consumed > 0.0 and trip.actual_fuel > 0.0:
                excess = trip.actual_fuel - norm_consumed
                trip.fuel_theft_suspected = bool(excess > 15.0 and (trip.actual_fuel / norm_consumed) >= 1.35)
            else:
                trip.fuel_theft_suspected = False

    @api.depends('total_fuel_cost', 'consumed_fuel_cost', 'actual_distance', 'actual_fuel', 'planned_distance', 'start_odometer', 'end_odometer')
    def _compute_trip_costs(self):
        for trip in self:
            trip.total_trip_cost = trip.consumed_fuel_cost if trip.consumed_fuel_cost > 0.0 else trip.total_fuel_cost
            dist = trip.actual_distance or (trip.end_odometer - trip.start_odometer if (trip.end_odometer and trip.start_odometer and trip.end_odometer > trip.start_odometer) else 0.0) or trip.planned_distance or 0.0
            if dist > 0.0:
                trip.cost_per_km = round(trip.total_trip_cost / dist, 2)
                trip.fuel_consumption_rate = round((trip.actual_fuel / dist) * 100.0, 2)
            else:
                trip.cost_per_km = 0.0
                trip.fuel_consumption_rate = 0.0

    @api.onchange('planned_distance', 'vehicle_id')
    def _onchange_planned_distance(self):
        if self.planned_distance and self.vehicle_id:
            rate = self.vehicle_id.expected_fuel_consumption or 12.0
            if not self.expected_fuel or self.expected_fuel == 0.0:
                self.expected_fuel = round((self.planned_distance * rate) / 100.0, 2)

    @api.depends('actual_distance', 'planned_distance', 'actual_duration', 'planned_duration', 'actual_fuel', 'expected_fuel', 'start_odometer', 'end_odometer')
    def _compute_variances(self):
        for trip in self:
            # Section 29 Reconciliation Formulas
            dist = trip.actual_distance or (trip.end_odometer - trip.start_odometer if (trip.end_odometer and trip.start_odometer and trip.end_odometer > trip.start_odometer) else 0.0) or (trip.planned_distance or 0.0)
            trip.variance_distance = round(dist - (trip.planned_distance or 0.0), 2)
            trip.variance_duration = round((trip.actual_duration or 0.0) - (trip.planned_duration or 0.0), 2)
            trip.variance_fuel = round((trip.actual_fuel or 0.0) - (trip.expected_fuel or 0.0), 2)

    @api.depends('vehicle_id', 'vehicle_id.gps_device_id')
    def _compute_gps_device(self):
        for trip in self:
            trip.gps_device_id = trip.vehicle_id.gps_device_id if trip.vehicle_id else False

    @api.depends('gps_device_id', 'gps_device_id.status')
    def _compute_gps_status(self):
        for trip in self:
            if not trip.gps_device_id:
                trip.gps_status = 'no_device'
            elif trip.gps_device_id.status == 'active':
                trip.gps_status = 'online'
            else:
                trip.gps_status = 'offline'

    @api.depends('vehicle_id.live_fuel_level', 'gps_device_id.fuel_level')
    def _compute_current_fuel(self):
        for trip in self:
            trip.current_fuel = (
                trip.vehicle_id.live_fuel_level
                or (trip.gps_device_id and trip.gps_device_id.fuel_level)
                or 0.0
            )

    @api.depends('actual_departure', 'actual_arrival')
    def _compute_actual_duration(self):
        for trip in self:
            if trip.actual_departure and trip.actual_arrival:
                delta = trip.actual_arrival - trip.actual_departure
                trip.actual_duration = round(delta.total_seconds() / 3600.0, 2)
            else:
                trip.actual_duration = 0.0

    @api.depends('cargo_amount_qty', 'cargo_tariff_unit_price')
    def _compute_cargo_total_tariff(self):
        for rec in self:
            rec.cargo_total_tariff = (rec.cargo_amount_qty or 0.0) * (rec.cargo_tariff_unit_price or 0.0)

    @api.constrains('planned_departure', 'planned_arrival')
    def _check_planned_dates(self):
        for trip in self:
            if trip.planned_departure and trip.planned_arrival and trip.planned_arrival < trip.planned_departure:
                raise ValidationError(_("Planned arrival (%s) cannot be earlier than planned departure (%s).") % (
                    trip.planned_arrival, trip.planned_departure
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('top.fleet.trip') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # WORKFLOW ACTIONS
    # -------------------------------------------------------------------------
    def action_view_on_map(self):
        self.ensure_one()
        return self.vehicle_id.action_view_on_map()

    def action_confirm(self):
        for trip in self:
            if trip.state != 'draft':
                raise UserError(_("Only draft trips can be confirmed."))
            v_ok, v_msg = trip.vehicle_id.check_availability(trip.planned_departure, trip.planned_arrival, exclude_trip_id=trip.id)
            if not v_ok:
                raise UserError(v_msg)
            d_ok, d_msg = trip.driver_id.check_availability(trip.planned_departure, trip.planned_arrival, exclude_trip_id=trip.id)
            if not d_ok:
                raise UserError(d_msg)

            trip.write({'state': 'ready'})
            trip.vehicle_id.write({'operational_status': 'assigned'})
            trip.driver_id.write({'driver_status': 'assigned'})
            trip.message_post(body=_("Trip confirmed and marked as ready for dispatch."))

    def action_dispatch(self):
        """Dispatches the trip directly, skipping pre-dispatch wizard since inspection is done in advance."""
        now = fields.Datetime.now()
        for trip in self:
            if trip.state != 'ready':
                raise UserError(_("Only trips in 'Ready / Assigned' status can be dispatched."))

            # Auto-link latest approved inspection if not already set
            if not trip.inspection_id and trip.vehicle_id.last_inspection_id:
                trip.inspection_id = trip.vehicle_id.last_inspection_id.id

            live_fuel = trip.vehicle_id.live_fuel_level or (trip.vehicle_id.gps_device_id and trip.vehicle_id.gps_device_id.fuel_level) or 0.0
            start_odo = trip.start_odometer or trip.vehicle_id.gps_device_id.odometer or trip.vehicle_id.odometer or 0.0
            start_fuel = trip.start_fuel or (trip.inspection_id.fuel_level if trip.inspection_id and trip.inspection_id.fuel_level else live_fuel)
            start_fuel_lvl = trip.start_fuel_level or (trip.inspection_id.fuel_gauge if trip.inspection_id and trip.inspection_id.fuel_gauge else 'half')

            trip_vals = {
                'state': 'dispatched',
                'actual_departure': now,
                'dispatch_date': now,
                'dispatched_by_id': self.env.user.id,
                'start_odometer': start_odo,
                'start_fuel': start_fuel,
                'start_fuel_level': start_fuel_lvl,
            }
            # Auto-populate checklist flags from the linked approved inspection
            if trip.inspection_id:
                for f in ('chk_tires', 'chk_engine', 'chk_oil', 'chk_coolant', 'chk_brakes', 'chk_lights',
                          'chk_spare_tire', 'chk_tools', 'chk_fire_extinguisher', 'chk_first_aid',
                          'chk_body_condition', 'chk_gps_online', 'chk_documents_valid'):
                    if hasattr(trip.inspection_id, f):
                        trip_vals[f] = getattr(trip.inspection_id, f)
            else:
                for f in ('chk_tires', 'chk_engine', 'chk_oil', 'chk_coolant', 'chk_brakes', 'chk_lights',
                          'chk_spare_tire', 'chk_tools', 'chk_fire_extinguisher', 'chk_first_aid',
                          'chk_body_condition', 'chk_gps_online', 'chk_documents_valid'):
                    trip_vals[f] = True

            trip_vals['chk_driver_confirmed'] = True
            trip.write(trip_vals)

            trip.vehicle_id.write({'operational_status': 'on_trip'})
            trip.driver_id.write({'driver_status': 'on_trip'})
            if trip.backup_driver_id:
                trip.backup_driver_id.write({'driver_status': 'on_trip'})

            for req in (trip.request_ids | trip.request_id):
                if req.state != 'in_transit':
                    req_vals = {}
                    if 'dispatched' in dict(req._fields['state'].selection):
                        req_vals['state'] = 'dispatched'
                    req.write(req_vals)
                    req.message_post(
                        body=_("Vehicle <strong>%s</strong> dispatched for mission by <strong>%s</strong>.<br/>"
                               "Inspection: <strong>%s</strong> | Start Odometer: %s km | Fuel: %s") % (
                            trip.vehicle_id.name, self.env.user.name,
                            trip.inspection_id.name if trip.inspection_id else _("Verified in Advance"),
                            start_odo, start_fuel_lvl
                        )
                    )

            trip.message_post(
                body=_("Vehicle <strong>%s</strong> dispatched directly into service by <strong>%s</strong>.<br/>"
                       "Pre-Trip Inspection: <strong>%s</strong> | Start Odometer: %s km | Fuel: %s") % (
                    trip.vehicle_id.name, self.env.user.name,
                    trip.inspection_id.name if trip.inspection_id else _("Verified in Advance"),
                    start_odo, start_fuel_lvl
                )
            )

    def action_open_dispatch_wizard(self):
        self.ensure_one()
        live_fuel = self.vehicle_id.live_fuel_level or (self.vehicle_id.gps_device_id and self.vehicle_id.gps_device_id.fuel_level) or 0.0
        return {
            'name': _('Pre-Dispatch Inspection Checklist'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.fleet.dispatch.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_trip_id': self.id,
                'default_start_odometer': self.vehicle_id.gps_device_id.odometer or self.vehicle_id.odometer or 0.0,
                'default_start_fuel': live_fuel,
            }
        }

    def action_open_return_wizard(self):
        """Opens Post-Trip Return Checklist Wizard."""
        self.ensure_one()
        end_odo = self.gps_device_id.odometer if (self.gps_device_id and self.gps_device_id.odometer) else (self.start_odometer or 0.0)
        live_fuel = self.vehicle_id.live_fuel_level or (self.vehicle_id.gps_device_id and self.vehicle_id.gps_device_id.fuel_level) or 0.0
        return {
            'name': _('Post-Trip Return Inspection Checklist'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.trip.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_trip_id': self.id,
                'default_end_odometer': end_odo,
                'default_end_fuel': live_fuel,
            }
        }

    def action_in_transit(self):
        for trip in self:
            if trip.state != 'dispatched':
                raise UserError(_("Trip must be dispatched before moving to in-transit status."))
            trip.write({'state': 'in_transit'})
            if trip.request_id and trip.request_id.state != 'in_transit':
                trip.request_id.write({'state': 'in_transit'})
            for req in trip.request_ids:
                if req.state != 'in_transit':
                    req.write({'state': 'in_transit'})
            trip.message_post(body=_("Vehicle is actively in transit."))

    def action_attach_transport_request(self, request_id):
        """Attaches an additional transport request to this trip, creating corresponding stops."""
        self.ensure_one()
        req = self.env['top.transport.request'].browse(request_id)
        if not req.exists():
            raise UserError(_("Transport request not found."))
        
        self.request_ids = [(4, req.id)]
        req.write({
            'trip_id': self.id,
            'assigned_vehicle_id': self.vehicle_id.id,
            'assigned_driver_id': self.driver_id.id,
            'state': 'assigned' if self.state in ['draft', 'ready'] else 'in_transit',
        })
        
        # Add stops for the request's origin and destination or its intermediate stops
        seq = (max(self.waypoint_ids.mapped('sequence')) + 10) if self.waypoint_ids else 10
        if req.stop_ids:
            for st in req.stop_ids:
                self.env['top.fleet.trip.waypoint'].create({
                    'trip_id': self.id,
                    'sequence': seq,
                    'location_id': st.location_id.id if st.location_id else False,
                    'location_name': st.location_name,
                    'stop_type': st.stop_type,
                    'request_id': req.id,
                    'cargo_or_passenger_notes': st.cargo_or_passenger_notes,
                    'notes': st.notes,
                    'state': 'pending',
                })
                seq += 10
        else:
            self.env['top.fleet.trip.waypoint'].create({
                'trip_id': self.id,
                'sequence': seq,
                'location_id': req.origin_location_id.id if req.origin_location_id else False,
                'location_name': req.origin,
                'stop_type': 'pickup',
                'request_id': req.id,
                'cargo_or_passenger_notes': req.cargo_description or (_("%s Passengers") % req.passenger_count),
                'state': 'pending',
            })
            self.env['top.fleet.trip.waypoint'].create({
                'trip_id': self.id,
                'sequence': seq + 10,
                'location_id': req.destination_location_id.id if req.destination_location_id else False,
                'location_name': req.destination,
                'stop_type': 'delivery',
                'request_id': req.id,
                'cargo_or_passenger_notes': req.cargo_description or (_("%s Passengers") % req.passenger_count),
                'state': 'pending',
            })
        
        self.message_post(
            body=_("Consolidated additional Transport Request <strong>%s</strong> into this trip. Pickup & delivery waypoints appended.") % req.name
        )
        req.message_post(
            body=_("Attached to consolidated Trip <a href='#' data-oe-model='top.fleet.trip' data-oe-id='%s'>%s</a>.") % (self.id, self.name)
        )

    def action_reconcile(self):
        for trip in self:
            if trip.state != 'completed':
                raise UserError(_("Only completed trips can be reconciled."))
            trip.write({'state': 'reconciled'})
            if trip.request_id and trip.request_id.state != 'reconciled':
                trip.request_id.write({'state': 'reconciled'})
            trip.message_post(
                body=_("<strong>Trip Reconciled</strong><br/>Distance Variance: %s km<br/>Duration Variance: %s hrs<br/>Fuel Variance: %s L<br/>Consumption Rate: %s L/100km") % (
                    trip.variance_distance, trip.variance_duration, trip.variance_fuel, trip.fuel_consumption_rate
                )
            )

    def action_close(self):
        for trip in self:
            if trip.state != 'reconciled':
                raise UserError(_("Only reconciled trips can be closed."))
            trip.write({'state': 'closed'})
            if trip.request_id and trip.request_id.state != 'closed':
                trip.request_id.write({'state': 'closed'})
            trip.message_post(body=_("Trip successfully closed."))

    def action_cancel(self):
        for trip in self:
            if trip.state in ['in_transit', 'completed', 'reconciled', 'closed']:
                raise UserError(_("Cannot cancel a trip that is in transit or completed."))
            trip.write({'state': 'cancelled'})
            trip.vehicle_id.write({'operational_status': 'available'})
            trip.driver_id.write({'driver_status': 'available'})
            if trip.request_id and trip.request_id.state != 'cancelled':
                trip.request_id.write({'state': 'approved'})
            trip.message_post(body=_("Trip cancelled."))

    # -------------------------------------------------------------------------
    # MOBILE & NOTIFICATION ACTIONS
    # -------------------------------------------------------------------------
    def action_record_fuel(self):
        """Quickly record fuel consumption/receipt from trip with automated odometer and utilization."""
        self.ensure_one()
        prev_log = self.env['top.fleet.fuel.log'].search([
            ('vehicle_id', '=', self.vehicle_id.id)
        ], order='date desc, id desc', limit=1)
        prev_odo = prev_log.odometer if (prev_log and prev_log.odometer) else (self.start_odometer or self.vehicle_id.odometer or 0.0)

        gps = self.vehicle_id.gps_device_id
        live_odo = self.current_odometer or self.vehicle_id.live_odometer or (gps.odometer if gps else 0.0)
        is_gps_live = bool(gps and live_odo > 0 and gps.status in ('online', 'standby'))
        refuel_odo = live_odo if is_gps_live else (self.current_odometer or self.vehicle_id.odometer or prev_odo)

        return {
            'name': _('Record Fuel Consumption'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.fleet.fuel.log',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_trip_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
                'default_driver_id': self.driver_id.id if self.driver_id else False,
                'default_start_odometer': prev_odo,
                'default_odometer': refuel_odo,
                'default_odometer_source': 'gps' if is_gps_live else 'manual',
            }
        }

    def action_report_accident(self):
        """Section 51 Mobile: Report incident/accident and upload photo directly from trip."""
        self.ensure_one()
        return {
            'name': _('Report Incident / Damage'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.fleet.accident',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_trip_id': self.id,
                'default_vehicle_id': self.vehicle_id.id,
                'default_driver_id': self.driver_id.id,
                'default_location': self.current_address or self.destination,
                'default_latitude': self.current_latitude,
                'default_longitude': self.current_longitude,
            }
        }

    @api.model
    def cron_check_trip_delays(self):
        """Section 50: Periodic scan for in-transit trips that have passed planned arrival."""
        now = fields.Datetime.now()
        delayed_trips = self.search([
            ('state', '=', 'in_transit'),
            ('planned_arrival', '<', now),
        ])
        officer_group = self.env.ref('top_logistics_fleet.group_fleet_officer', raise_if_not_found=False)
        officer_user = officer_group.users[0] if officer_group and officer_group.users else self.env.user
        activity_type = self.env.ref('top_logistics_fleet.mail_act_trip_delay', raise_if_not_found=False)
        template = self.env.ref('top_logistics_fleet.mail_template_trip_delay', raise_if_not_found=False)

        for trip in delayed_trips:
            if activity_type:
                existing = self.env['mail.activity'].search([
                    ('res_model', '=', 'top.fleet.trip'),
                    ('res_id', '=', trip.id),
                    ('activity_type_id', '=', activity_type.id),
                ], limit=1)
                if not existing:
                    trip.activity_schedule(
                        'top_logistics_fleet.mail_act_trip_delay',
                        summary=_("Trip Delay Detected: %s past planned arrival (%s)") % (trip.name, trip.planned_arrival),
                        user_id=officer_user.id,
                    )
                    if template:
                        template.send_mail(trip.id, force_send=False)

