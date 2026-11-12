# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class FleetVehicleInspection(models.Model):
    _name = 'top.fleet.vehicle.inspection'
    _description = 'Vehicle Technical & Safety Inspection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'inspection_date desc, id desc'

    name = fields.Char(
        string='Inspection Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        tracking=True,
        index=True,
    )
    license_plate = fields.Char(
        related='vehicle_id.license_plate',
        string='License Plate',
        readonly=True,
    )
    vehicle_model_id = fields.Many2one(
        related='vehicle_id.model_id',
        string='Vehicle Model',
        readonly=True,
    )
    vin_sn = fields.Char(
        related='vehicle_id.vin_sn',
        string='Chassis / VIN Number',
        readonly=True,
    )
    transmission = fields.Selection(
        related='vehicle_id.transmission',
        string='Transmission',
        readonly=True,
    )
    fuel_type = fields.Selection(
        related='vehicle_id.fuel_type',
        string='Fuel Type',
        readonly=True,
    )
    seats = fields.Integer(
        related='vehicle_id.seats',
        string='Seats',
        readonly=True,
    )
    operational_status = fields.Selection(
        related='vehicle_id.operational_status',
        string='Vehicle Operational Status',
        readonly=True,
    )
    service_status = fields.Selection(
        related='vehicle_id.service_status',
        string='Maintenance Status',
        readonly=True,
    )
    last_service_date = fields.Date(
        related='vehicle_id.last_service_date',
        string='Last Service Date',
        readonly=True,
    )
    next_service_date = fields.Date(
        related='vehicle_id.next_service_date',
        string='Next Service Due',
        readonly=True,
    )
    document_compliance_status = fields.Char(
        related='vehicle_id.document_compliance_status',
        string='Document Compliance',
        readonly=True,
    )
    capacity_cargo_kg = fields.Float(
        related='vehicle_id.capacity_cargo_kg',
        string='Rated Load Capacity (kg)',
        readonly=True,
    )

    # Driver Details (Fetched from Employee Module)
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver (Employee)',
        domain="[('is_driver', '=', True)]",
        tracking=True,
        help="Driver assigned or inspecting this vehicle, selected from Employee module.",
    )
    driver_license_number = fields.Char(
        related='driver_id.driver_license_number',
        string='Driver License Number',
        readonly=True,
    )
    license_category = fields.Selection(
        related='driver_id.license_category',
        string='License Category',
        readonly=True,
    )
    driver_license_expiry = fields.Date(
        related='driver_id.license_expiry_date',
        string='License Expiration',
        readonly=True,
    )
    driver_license_compliance = fields.Char(
        related='driver_id.license_compliance_status',
        string='Driver License Status',
        readonly=True,
    )
    driver_phone = fields.Char(
        related='driver_id.work_phone',
        string='Driver Phone',
        readonly=True,
    )
    driver_department_id = fields.Many2one(
        related='driver_id.department_id',
        string='Driver Department',
        readonly=True,
    )

    fleet_type = fields.Selection([
        ('light', 'Light Fleet'),
        ('heavy', 'Heavy Fleet'),
    ], string='Fleet Type', compute='_compute_fleet_type', store=True, readonly=False, tracking=True)

    inspector_id = fields.Many2one(
        'res.users',
        string='Inspector / Officer',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    inspection_date = fields.Datetime(
        string='Inspection Date & Time',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    validity_duration = fields.Selection([
        ('24h', '24 Hours'),
        ('48h', '48 Hours'),
        ('7d', '7 Days'),
        ('14d', '14 Days'),
        ('30d', '30 Days'),
        ('custom', 'Custom Expiry Date'),
    ], string='Validity Window', default='7d', required=True, tracking=True)
    valid_until = fields.Datetime(
        string='Valid Until',
        compute='_compute_valid_until',
        store=True,
        readonly=False,
        help='Inspection validity window. Vehicles are approved and available for trip assignment during this window.',
    )
    inspection_type = fields.Selection([
        ('pre_trip', 'Pre-Trip Staging Inspection'),
        ('daily', 'Daily Morning Routine Check'),
        ('weekly', 'Weekly Comprehensive Audit'),
        ('post_trip', 'Post-Trip Debrief Inspection'),
        ('periodic', 'Periodic Safety & Maintenance Inspection'),
    ], string='Inspection Type', default='pre_trip', required=True, tracking=True)

    odometer = fields.Float(string='Current Odometer (km)', required=True, tracking=True)
    fuel_level = fields.Float(string='Fuel Level (L)', help='Estimated fuel level in litres')
    fuel_gauge = fields.Selection([
        ('quarter', '1/4 Tank'),
        ('half', '1/2 Tank'),
        ('three_quarter', '3/4 Tank'),
        ('full', 'Full Tank'),
    ], string='Fuel Gauge Reading', default='full')

    # Mechanical & Fluids
    chk_tires = fields.Boolean(string='Tires Condition & Pressure', default=True)
    chk_engine = fields.Boolean(string='Engine Sound & Mountings', default=True)
    chk_oil = fields.Boolean(string='Engine Oil Level & Condition', default=True)
    chk_coolant = fields.Boolean(string='Coolant & Radiator Fluid', default=True)
    chk_brakes = fields.Boolean(string='Foot & Parking Brakes', default=True)
    chk_lights = fields.Boolean(string='All Lights, Indicators & Hazards', default=True)

    # Safety & Equipment
    chk_spare_tire = fields.Boolean(string='Spare Tire Present & Inflated', default=True)
    chk_tools = fields.Boolean(string='Jack & Wheel Spanner', default=True)
    chk_fire_extinguisher = fields.Boolean(string='Fire Extinguisher Valid & Charged', default=True)
    chk_first_aid = fields.Boolean(string='First Aid Kit Present', default=True)
    chk_warning_triangles = fields.Boolean(string='Warning Triangles Present', default=True)
    chk_seatbelts = fields.Boolean(string='Seatbelts Functional', default=True)

    # Body, Glass & Mirrors
    chk_body_condition = fields.Boolean(string='Body Condition (No Unrecorded Dents)', default=True)
    chk_windshield_wipers = fields.Boolean(string='Windshield & Wipers Operational', default=True)
    chk_mirrors = fields.Boolean(string='Rearview & Side Mirrors Intact', default=True)

    # Telematics & Documentation
    chk_gps_online = fields.Boolean(string='GPS Telematics Online', default=True)
    chk_documents_valid = fields.Boolean(string='Vehicle Registration & Insurance Valid', default=True)

    # Heavy Fleet Specific Checklist Items
    chk_air_brake_pressure = fields.Boolean(string='Air Brake Pressure & Tanks', default=True)
    chk_fifth_wheel_coupling = fields.Boolean(string='Fifth Wheel / Coupling Pin Checked', default=True)
    chk_cargo_tie_downs = fields.Boolean(string='Cargo Chains / Straps / Tarps Ready', default=True)

    # Assessment & Decision
    result = fields.Selection([
        ('passed', 'Passed - Fit for Dispatch'),
        ('passed_with_notes', 'Passed with Minor Notes'),
        ('failed', 'Failed - Unfit for Service / Grounded'),
    ], string='Inspection Result', default='passed', required=True, tracking=True)

    defects_observed = fields.Text(string='Defects Observed')
    corrective_action = fields.Text(string='Required Corrective Actions')
    notes = fields.Text(string='General Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved / Passed'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected / Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', readonly=True, tracking=True)

    trip_id = fields.Many2one(
        'top.fleet.trip',
        string='Associated Trip',
        help='Trip this inspection was associated with or dispatched against.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            if self.vehicle_id.odometer:
                self.odometer = self.vehicle_id.odometer
            if hasattr(self.vehicle_id, 'driver_id') and self.vehicle_id.driver_id:
                self.driver_id = self.vehicle_id.driver_id

    @api.depends('vehicle_id')
    def _compute_fleet_type(self):
        for rec in self:
            if rec.vehicle_id and hasattr(rec.vehicle_id, 'fleet_type') and rec.vehicle_id.fleet_type:
                rec.fleet_type = rec.vehicle_id.fleet_type
            elif not rec.fleet_type:
                rec.fleet_type = 'light'

    @api.depends('inspection_date', 'validity_duration')
    def _compute_valid_until(self):
        for rec in self:
            if rec.inspection_date:
                dur = rec.validity_duration or '7d'
                if dur == '24h':
                    rec.valid_until = rec.inspection_date + timedelta(hours=24)
                elif dur == '48h':
                    rec.valid_until = rec.inspection_date + timedelta(hours=48)
                elif dur == '7d':
                    rec.valid_until = rec.inspection_date + timedelta(days=7)
                elif dur == '14d':
                    rec.valid_until = rec.inspection_date + timedelta(days=14)
                elif dur == '30d':
                    rec.valid_until = rec.inspection_date + timedelta(days=30)
            else:
                rec.valid_until = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('top.fleet.vehicle.inspection') or _('New')
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft inspections can be approved."))
            if rec.result == 'failed':
                rec.write({'state': 'rejected'})
                if rec.vehicle_id:
                    rec.vehicle_id.write({'operational_status': 'maintenance'})
                    rec.vehicle_id.message_post(
                        body=_("⚠️ <strong>Vehicle Grounded:</strong> Failed technical inspection <a href='#' data-oe-model='top.fleet.vehicle.inspection' data-oe-id='%s'>%s</a>.<br/><strong>Defects:</strong> %s") % (
                            rec.id, rec.name, rec.defects_observed or _("See inspection report")
                        )
                    )
            else:
                rec.write({'state': 'approved'})
                if rec.vehicle_id:
                    if rec.vehicle_id.operational_status == 'maintenance':
                        rec.vehicle_id.write({'operational_status': 'available'})
                    valid_str = rec.valid_until.strftime('%Y-%m-%d %H:%M') if rec.valid_until else _("N/A")
                    rec.vehicle_id.message_post(
                        body=_("✅ <strong>Inspection Approved:</strong> Vehicle passed technical inspection <a href='#' data-oe-model='top.fleet.vehicle.inspection' data-oe-id='%s'>%s</a> (Result: %s). Valid until: %s.") % (
                            rec.id, rec.name, dict(rec._fields['result'].selection).get(rec.result), valid_str
                        )
                    )
            if rec.vehicle_id:
                rec.vehicle_id._compute_inspection_metrics()

    action_confirm = action_approve

    def action_reject(self):
        for rec in self:
            rec.write({
                'state': 'rejected',
                'result': 'failed',
            })
            if rec.vehicle_id:
                rec.vehicle_id.write({'operational_status': 'maintenance'})
                rec.vehicle_id.message_post(
                    body=_("❌ <strong>Inspection Rejected:</strong> Vehicle grounded by %s. Defects: %s") % (
                        self.env.user.name, rec.defects_observed or _("Defects noted during technical inspection.")
                    )
                )
                rec.vehicle_id._compute_inspection_metrics()

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})
            if rec.vehicle_id:
                rec.vehicle_id._compute_inspection_metrics()

    def action_reset_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})
            if rec.vehicle_id:
                rec.vehicle_id._compute_inspection_metrics()

