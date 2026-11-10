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
    valid_until = fields.Datetime(
        string='Valid Until',
        compute='_compute_valid_until',
        store=True,
        readonly=False,
        help='Inspection validity window. Typically valid for 24-48 hours for fast-track dispatch.',
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
        ('confirmed', 'Confirmed'),
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

    @api.depends('vehicle_id')
    def _compute_fleet_type(self):
        for rec in self:
            if rec.vehicle_id and hasattr(rec.vehicle_id, 'fleet_type') and rec.vehicle_id.fleet_type:
                rec.fleet_type = rec.vehicle_id.fleet_type
            elif not rec.fleet_type:
                rec.fleet_type = 'light'

    @api.depends('inspection_date')
    def _compute_valid_until(self):
        for rec in self:
            if rec.inspection_date:
                rec.valid_until = rec.inspection_date + timedelta(hours=48)
            else:
                rec.valid_until = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('top.fleet.vehicle.inspection') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft inspections can be confirmed."))
            rec.write({'state': 'confirmed'})
            # Update vehicle latest inspection data and status if failed
            if rec.vehicle_id:
                if rec.result == 'failed':
                    rec.vehicle_id.write({
                        'operational_status': 'maintenance',
                    })
                    rec.vehicle_id.message_post(
                        body=_("⚠️ <strong>Vehicle Grounded:</strong> Failed technical inspection <a href='#' data-oe-model='top.fleet.vehicle.inspection' data-oe-id='%s'>%s</a>.<br/><strong>Defects:</strong> %s") % (
                            rec.id, rec.name, rec.defects_observed or _("See inspection report")
                        )
                    )
                else:
                    rec.vehicle_id.message_post(
                        body=_("✅ <strong>Inspection Confirmed:</strong> Passed inspection <a href='#' data-oe-model='top.fleet.vehicle.inspection' data-oe-id='%s'>%s</a> (Result: %s). Valid until: %s.") % (
                            rec.id, rec.name, dict(rec._fields['result'].selection).get(rec.result), rec.valid_until
                        )
                    )

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})

    def action_reset_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})

