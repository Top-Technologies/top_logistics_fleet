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
    odometer = fields.Float(string='Odometer at Refuel (km)', required=True)
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

    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        if self.trip_id:
            if not self.vehicle_id and self.trip_id.vehicle_id:
                self.vehicle_id = self.trip_id.vehicle_id
            if not self.driver_id and self.trip_id.driver_id:
                self.driver_id = self.trip_id.driver_id
            if not self.odometer:
                self.odometer = (
                    self.trip_id.current_odometer
                    or self.trip_id.end_odometer
                    or self.trip_id.start_odometer
                    or (self.trip_id.vehicle_id.odometer if self.trip_id.vehicle_id else 0.0)
                )

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            if not self.odometer and self.vehicle_id.odometer:
                self.odometer = self.vehicle_id.odometer
            if not self.trip_id:
                active_trip = self.env['top.fleet.trip'].search([
                    ('vehicle_id', '=', self.vehicle_id.id),
                    ('state', 'in', ['dispatched', 'in_transit', 'ready']),
                ], order='actual_departure desc, planned_departure desc, id desc', limit=1)
                if active_trip:
                    self.trip_id = active_trip.id
                    if not self.driver_id and active_trip.driver_id:
                        self.driver_id = active_trip.driver_id

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
        records = super().create(vals_list)
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
