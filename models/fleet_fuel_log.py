from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FleetFuelLog(models.Model):
    _name = 'top.fleet.fuel.log'
    _description = 'Vehicle Fuel Transaction Log'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, default=lambda self: _('New'))
    date = fields.Datetime(string='Date & Time', default=fields.Datetime.now, required=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, index=True)
    driver_id = fields.Many2one('hr.employee', string='Driver', domain="[('is_driver', '=', True)]")
    trip_id = fields.Many2one('top.fleet.trip', string='Associated Trip', index=True)
    
    # Odometer & Telematics Fields
    start_odometer = fields.Float(
        string='Starting Odometer (km)',
        
        help='Odometer reading at the start of the leg or previous refueling point.'
    )
    odometer = fields.Float(
        string='Odometer at Refuel (km)',
        required=True,
        
        help='Odometer reading at the time of refueling.'
    )
    odometer_diff = fields.Float(
        string='Distance Covered (km)',
        compute='_compute_utilization',
        store=True,
        readonly=False,
        
        help='Difference between refuel odometer and starting odometer.'
    )
    odometer_source = fields.Selection([
        ('gps', 'Automatic (Live GPS Telematics)'),
        ('manual', 'Manual Input (GPS Inactive/Off)'),
    ], string='Telemetry Source', default='manual')
    gps_available = fields.Boolean(
        string='GPS Available',
        compute='_compute_gps_available',
    )

    # Fuel Utilization & Efficiency KPIs
    consumption_rate = fields.Float(
        string='Consumption Rate (L/100km)',
        compute='_compute_utilization',
        store=True,
        digits=(10, 2),
        
        help='Calculated fuel consumption rate in Litres per 100 km for this leg.'
    )
    km_per_liter = fields.Float(
        string='Fuel Economy (km/L)',
        compute='_compute_utilization',
        store=True,
        digits=(10, 2),
        
        help='Kilometers driven per litre of fuel consumed.'
    )
    benchmark_rate = fields.Float(
        string='Expected Benchmark (L/100km)',
        related='vehicle_id.expected_fuel_consumption',
        readonly=True,
        help='Target standard consumption rate defined on the vehicle.'
    )
    consumption_variance = fields.Float(
        string='Variance vs Benchmark (%)',
        compute='_compute_utilization',
        store=True,
        digits=(10, 1),
        help='Percentage deviation from the target benchmark rate.'
    )
    utilization_status = fields.Selection([
        ('efficient', 'Optimal / Under Benchmark'),
        ('normal', 'Normal / Within Norm'),
        ('high', 'High Consumption / Above Norm'),
        ('no_distance', 'No Distance Recorded'),
    ], string='Utilization Status', compute='_compute_utilization', store=True)

    fuel_station = fields.Char(string='Fuel Station / Location', required=True)
    fuel_type = fields.Selection([
        ('diesel', 'Diesel'),
        ('petrol_regular', 'Petrol (Regular)'),
        ('petrol_super', 'Petrol (Super)'),
        ('cng', 'CNG'),
        ('electric', 'Electric Recharge (kWh)'),
    ], string='Fuel Type', default='diesel', required=True)

    quantity = fields.Float(string='Quantity (Litres)', required=True)
    unit_price = fields.Float(string='Unit Price', required=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)

    payment_method = fields.Selection([
        ('fuel_card', 'Company Fuel Card'),
        ('cash', 'Petty Cash / Reimbursement'),
        ('voucher', 'Fuel Coupon / Voucher'),
        ('company_account', 'Direct Invoiced Account'),
    ], string='Payment Method', default='fuel_card', required=True)

    receipt = fields.Binary(string='Receipt Attachment', attachment=True)
    receipt_filename = fields.Char(string='Receipt Filename')
    notes = fields.Text(string='Notes / Station Remarks')

    @api.depends('quantity', 'unit_price')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = round(rec.quantity * rec.unit_price, 2)

    @api.depends('vehicle_id', 'vehicle_id.gps_device_id', 'vehicle_id.gps_device_id.status')
    def _compute_gps_available(self):
        for rec in self:
            gps = rec.vehicle_id.gps_device_id if rec.vehicle_id else False
            rec.gps_available = bool(
                gps and (gps.status in ('online', 'standby') or rec.vehicle_id.live_odometer > 0)
            )

    @api.depends('odometer', 'start_odometer', 'quantity', 'vehicle_id.expected_fuel_consumption')
    def _compute_utilization(self):
        for rec in self:
            start = rec.start_odometer or 0.0
            end = rec.odometer or 0.0
            diff = max(0.0, end - start)
            rec.odometer_diff = round(diff, 2)

            qty = rec.quantity or 0.0
            benchmark = rec.vehicle_id.expected_fuel_consumption or 12.0

            if diff > 0.0 and qty > 0.0:
                rate = round((qty / diff) * 100.0, 2)
                rec.consumption_rate = rate
                rec.km_per_liter = round(diff / qty, 2)
                if benchmark > 0.0:
                    rec.consumption_variance = round(((rate - benchmark) / benchmark) * 100.0, 1)
                else:
                    rec.consumption_variance = 0.0

                if rate <= benchmark * 0.95:
                    rec.utilization_status = 'efficient'
                elif rate <= benchmark * 1.15:
                    rec.utilization_status = 'normal'
                else:
                    rec.utilization_status = 'high'
            else:
                rec.consumption_rate = 0.0
                rec.km_per_liter = 0.0
                rec.consumption_variance = 0.0
                rec.utilization_status = 'no_distance'

    def action_fetch_gps_odometer(self):
        """Fetch real-time live odometer from vehicle GPS telematics tracker."""
        self.ensure_one()
        if self.vehicle_id and self.vehicle_id.gps_device_id:
            live_odo = self.vehicle_id.live_odometer or self.vehicle_id.gps_device_id.odometer
            if live_odo:
                self.odometer = live_odo
                self.odometer_source = 'gps'

    def _get_previous_odometer(self, vehicle_id, exclude_id=False):
        domain = [('vehicle_id', '=', vehicle_id)]
        if exclude_id:
            domain.append(('id', '!=', exclude_id))
        prev_log = self.search(domain, order='date desc, id desc', limit=1)
        if prev_log and prev_log.odometer:
            return prev_log.odometer
        return False

    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        if self.trip_id:
            if not self.vehicle_id and self.trip_id.vehicle_id:
                self.vehicle_id = self.trip_id.vehicle_id
            if not self.driver_id and self.trip_id.driver_id:
                self.driver_id = self.trip_id.driver_id

            vehicle = self.vehicle_id or self.trip_id.vehicle_id
            gps = vehicle.gps_device_id if vehicle else False
            live_odo = vehicle.live_odometer or (gps.odometer if gps else 0.0) if vehicle else 0.0
            is_gps_live = bool(gps and live_odo > 0 and gps.status in ('online', 'standby'))
            self.odometer_source = 'gps' if is_gps_live else 'manual'

            # Starting odometer: previous refuel on vehicle or trip start
            if vehicle:
                prev_odo = self._get_previous_odometer(vehicle.id, exclude_id=self._origin.id if self._origin else False)
                if prev_odo:
                    self.start_odometer = prev_odo
                elif self.trip_id.start_odometer:
                    self.start_odometer = self.trip_id.start_odometer

            # Ending odometer at refuel
            if is_gps_live:
                self.odometer = live_odo
            elif not self.odometer:
                self.odometer = (
                    self.trip_id.current_odometer
                    or self.trip_id.end_odometer
                    or self.trip_id.start_odometer
                    or (vehicle.odometer if vehicle else 0.0)
                )

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            gps = self.vehicle_id.gps_device_id
            live_odo = self.vehicle_id.live_odometer or (gps.odometer if gps else 0.0)
            is_gps_live = bool(gps and live_odo > 0 and gps.status in ('online', 'standby'))

            self.odometer_source = 'gps' if is_gps_live else 'manual'

            # Ending Odometer at Refuel
            if is_gps_live:
                self.odometer = live_odo
            elif not self.odometer and self.vehicle_id.odometer:
                self.odometer = self.vehicle_id.odometer

            # Starting Odometer: previous fuel log, or active trip start
            prev_odo = self._get_previous_odometer(self.vehicle_id.id, exclude_id=self._origin.id if self._origin else False)
            if prev_odo:
                self.start_odometer = prev_odo
            elif self.trip_id and self.trip_id.start_odometer:
                self.start_odometer = self.trip_id.start_odometer

            # Find active trip if not set
            if not self.trip_id:
                active_trip = self.env['top.fleet.trip'].search([
                    ('vehicle_id', '=', self.vehicle_id.id),
                    ('state', 'in', ['dispatched', 'in_transit', 'ready']),
                ], order='actual_departure desc, planned_departure desc, id desc', limit=1)
                if active_trip:
                    self.trip_id = active_trip.id
                    if not self.driver_id and active_trip.driver_id:
                        self.driver_id = active_trip.driver_id
                    if not self.start_odometer and active_trip.start_odometer:
                        self.start_odometer = active_trip.start_odometer

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('top.fleet.fuel.log') or _('FUEL')
            # Auto-link trip if vehicle is on active trip at the logged time
            if not vals.get('trip_id') and vals.get('vehicle_id'):
                log_dt = vals.get('date') or fields.Datetime.now()
                active_trip = self.env['top.fleet.trip'].search([
                    ('vehicle_id', '=', vals['vehicle_id']),
                    ('state', 'in', ['dispatched', 'in_transit', 'ready', 'completed']),
                    '|',
                    '&', ('actual_departure', '<=', log_dt), ('actual_arrival', '>=', log_dt),
                    '&', ('planned_departure', '<=', log_dt), ('planned_arrival', '>=', log_dt),
                ], limit=1)
                if not active_trip:
                    active_trip = self.env['top.fleet.trip'].search([
                        ('vehicle_id', '=', vals['vehicle_id']),
                        ('state', 'in', ['dispatched', 'in_transit']),
                    ], limit=1)
                if active_trip:
                    vals['trip_id'] = active_trip.id
                    if not vals.get('driver_id') and active_trip.driver_id:
                        vals['driver_id'] = active_trip.driver_id.id
            if vals.get('trip_id') and not vals.get('vehicle_id'):
                trip = self.env['top.fleet.trip'].browse(vals['trip_id'])
                if trip.exists():
                    vals['vehicle_id'] = trip.vehicle_id.id
                    if not vals.get('driver_id') and trip.driver_id:
                        vals['driver_id'] = trip.driver_id.id

            v_id = vals.get('vehicle_id')
            if v_id and not vals.get('start_odometer'):
                prev_odo = self._get_previous_odometer(v_id)
                if prev_odo:
                    vals['start_odometer'] = prev_odo
                elif vals.get('trip_id'):
                    t = self.env['top.fleet.trip'].browse(vals['trip_id'])
                    if t.exists() and t.start_odometer:
                        vals['start_odometer'] = t.start_odometer

        records = super().create(vals_list)
        for rec in records:
            if rec.odometer and rec.vehicle_id and rec.odometer > (rec.vehicle_id.odometer or 0.0):
                rec.vehicle_id.write({'odometer': rec.odometer})
        # Invalidate / trigger trip cost recomputations
        trips = records.mapped('trip_id')
        if trips:
            trips._compute_fuel_metrics()
            trips._compute_trip_costs()
        return records

    def write(self, vals):
        res = super().write(vals)
        trips = self.mapped('trip_id')
        if trips:
            trips._compute_fuel_metrics()
            trips._compute_trip_costs()
        return res
