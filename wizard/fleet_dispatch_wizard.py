from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FleetDispatchWizard(models.TransientModel):
    _name = 'top.fleet.dispatch.wizard'
    _description = 'Pre-Dispatch Vehicle Condition Checklist Wizard (Sections 17 & 35)'

    trip_id = fields.Many2one(
        'top.fleet.trip',
        string='Trip to Dispatch',
        required=True,
    )
    vehicle_id = fields.Many2one(related='trip_id.vehicle_id', string='Vehicle', readonly=True)
    driver_id = fields.Many2one(related='trip_id.driver_id', string='Driver', readonly=True)
    origin = fields.Char(related='trip_id.origin', string='Origin', readonly=True)
    destination = fields.Char(related='trip_id.destination', string='Destination', readonly=True)

    # Specific Vehicle Condition Checklist from Section 35
    chk_tires = fields.Boolean(string='1. Tires (Condition & Pressure OK)', default=True)
    chk_engine = fields.Boolean(string='2. Engine (Normal Sound & Operation)', default=True)
    chk_oil = fields.Boolean(string='3. Oil (Engine Oil Level Checked)', default=True)
    chk_coolant = fields.Boolean(string='4. Coolant & Radiator Fluids OK', default=True)
    chk_brakes = fields.Boolean(string='5. Brakes (Foot & Handbrake Tested)', default=True)
    chk_lights = fields.Boolean(string='6. Lights (Headlights, Signals & Brake Lights)', default=True)
    chk_spare_tire = fields.Boolean(string='7. Spare Tire (Present & Inflated)', default=True)
    chk_tools = fields.Boolean(string='8. Tools (Jack, Wheel Spanner Present)', default=True)
    chk_fire_extinguisher = fields.Boolean(string='9. Fire Extinguisher (Present & Valid)', default=True)
    chk_first_aid = fields.Boolean(string='10. First Aid Kit Present', default=True)
    chk_body_condition = fields.Boolean(string='11. Body Condition (No Unrecorded Dents)', default=True)

    # Operational Confirmations
    chk_driver_confirmed = fields.Boolean(string='Driver Fit for Duty & Briefed', default=True)
    chk_gps_online = fields.Boolean(string='GPS Tracker Transmitting Online', default=True)
    chk_documents_valid = fields.Boolean(string='Documents Physically Verified (Insurance, Registration)', default=True)

    # Initial Readings
    start_odometer = fields.Float(string='Starting Odometer (km)', required=True)
    start_fuel = fields.Float(string='Starting Fuel Level (L)', required=True, default=0.0)
    start_fuel_level = fields.Selection([
        ('quarter', '1/4 Tank'),
        ('half', '1/2 Tank'),
        ('three_quarter', '3/4 Tank'),
        ('full', 'Full Tank'),
    ], string='Starting Fuel Gauge', default='full', required=True)
    dispatch_notes = fields.Text(string='Dispatch Notes / Observations')

    def action_confirm_dispatch(self):
        self.ensure_one()
        trip = self.trip_id

        # Verify all safety items
        mandatory_checks = [
            (self.chk_tires, _("Tires Condition")),
            (self.chk_engine, _("Engine Check")),
            (self.chk_oil, _("Oil Level")),
            (self.chk_coolant, _("Coolant Level")),
            (self.chk_brakes, _("Brakes Test")),
            (self.chk_lights, _("Vehicle Lights")),
            (self.chk_spare_tire, _("Spare Tire")),
            (self.chk_tools, _("Tools & Jack")),
            (self.chk_fire_extinguisher, _("Fire Extinguisher")),
            (self.chk_first_aid, _("First Aid Kit")),
            (self.chk_body_condition, _("Body Inspection")),
            (self.chk_driver_confirmed, _("Driver Briefing")),
            (self.chk_gps_online, _("GPS Tracker Confirmation")),
            (self.chk_documents_valid, _("Documents Physical Verification")),
        ]

        failed = [label for passed, label in mandatory_checks if not passed]
        if failed:
            raise UserError(_("Cannot dispatch vehicle until all condition checklist items are verified: %s") % ", ".join(failed))

        now = fields.Datetime.now()
        trip_vals = {
            'state': 'in_transit',
            'actual_departure': now,
            'dispatch_date': now,
            'dispatched_by_id': self.env.user.id,
            'chk_tires': self.chk_tires,
            'chk_engine': self.chk_engine,
            'chk_oil': self.chk_oil,
            'chk_coolant': self.chk_coolant,
            'chk_brakes': self.chk_brakes,
            'chk_lights': self.chk_lights,
            'chk_spare_tire': self.chk_spare_tire,
            'chk_tools': self.chk_tools,
            'chk_fire_extinguisher': self.chk_fire_extinguisher,
            'chk_first_aid': self.chk_first_aid,
            'chk_body_condition': self.chk_body_condition,
            'chk_driver_confirmed': self.chk_driver_confirmed,
            'chk_gps_online': self.chk_gps_online,
            'chk_documents_valid': self.chk_documents_valid,
            'start_odometer': self.start_odometer,
            'start_fuel': self.start_fuel,
            'start_fuel_level': self.start_fuel_level,
        }
        trip.write(trip_vals)

        trip.vehicle_id.write({'operational_status': 'on_trip'})
        trip.driver_id.write({'driver_status': 'on_trip'})
        if trip.backup_driver_id:
            trip.backup_driver_id.write({'driver_status': 'on_trip'})

        if trip.request_id:
            trip.request_id.write({'state': 'in_transit'})
            trip.request_id.message_post(
                body=_("Vehicle <strong>%s</strong> dispatched into transit by <strong>%s</strong>.<br/>Start Odometer: %s km | Fuel: %s") % (
                    trip.vehicle_id.name, self.env.user.name, self.start_odometer, self.start_fuel_level
                )
            )

        trip.message_post(
            body=_("Pre-dispatch condition checklist passed (Section 35). Vehicle dispatched by %s.") % self.env.user.name
        )

        # Section 50: Send "Trip Dispatched" notification
        template_dispatched = self.env.ref('top_logistics_fleet.mail_template_trip_dispatched', raise_if_not_found=False)
        if template_dispatched:
            template_dispatched.send_mail(trip.id, force_send=False)

        activity_dispatched = self.env.ref('top_logistics_fleet.mail_act_trip_dispatched', raise_if_not_found=False)
        target_partner = trip.request_id.requester_id if trip.request_id else False
        if activity_dispatched and target_partner:
            trip.activity_schedule(
                'top_logistics_fleet.mail_act_trip_dispatched',
                summary=_("Trip %s Dispatched: Vehicle %s en route to %s") % (trip.name, trip.vehicle_id.name, trip.destination),
                user_id=target_partner.id,
            )

        return {'type': 'ir.actions.act_window_close'}
