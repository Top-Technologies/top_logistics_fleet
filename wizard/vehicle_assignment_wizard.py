from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class VehicleAssignmentWizard(models.TransientModel):
    _name = 'top.vehicle.assignment.wizard'
    _description = 'Vehicle & Driver Assignment Wizard'

    request_id = fields.Many2one(
        'top.transport.request',
        string='Transport Request',
        required=True,
    )
    requester_id = fields.Many2one(related='request_id.requester_id', string='Requester', readonly=True)
    origin = fields.Char(related='request_id.origin', string='Origin', readonly=True)
    destination = fields.Char(related='request_id.destination', string='Destination', readonly=True)
    required_date = fields.Datetime(related='request_id.required_date', string='Required Date', readonly=True)
    return_date = fields.Datetime(related='request_id.return_date', string='Return Date', readonly=True)
    vehicle_type_id = fields.Many2one(related='request_id.vehicle_type_id', string='Requested Vehicle Type', readonly=True)

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle to Assign',
        required=True,
    )
    vehicle_status_info = fields.Char(string='Vehicle Status', readonly=True)

    driver_id = fields.Many2one(
        'hr.employee',
        string='Primary Driver',
        required=True,
        domain="[('is_driver', '=', True)]",
    )
    driver_status_info = fields.Char(string='Driver Status', readonly=True)

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
    trip_type_id = fields.Many2one(
        'top.fleet.trip.type',
        string='Trip Type',
    )
    planned_distance = fields.Float(string='Planned Distance (km)')
    planned_duration = fields.Float(string='Planned Duration (Hours)')
    special_instructions = fields.Text(string='Special Instructions')

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and self.request_id:
            ok, msg = self.vehicle_id.check_availability(
                self.request_id.required_date, self.request_id.return_date
            )
            self.vehicle_status_info = _("Available") if ok else msg

    @api.onchange('driver_id')
    def _onchange_driver_id(self):
        if self.driver_id and self.request_id:
            ok, msg = self.driver_id.check_availability(
                self.request_id.required_date, self.request_id.return_date
            )
            self.driver_status_info = _("Available") if ok else msg

    def action_confirm_assignment(self):
        self.ensure_one()
        req = self.request_id

        # Section 12 Validation: Vehicle
        v_ok, v_msg = self.vehicle_id.check_availability(req.required_date, req.return_date)
        if not v_ok:
            raise ValidationError(_("Vehicle Assignment Error: %s") % v_msg)

        # Section 12 Validation: Driver
        d_ok, d_msg = self.driver_id.check_availability(req.required_date, req.return_date)
        if not d_ok:
            raise ValidationError(_("Driver Assignment Error: %s") % d_msg)

        # Check backup driver if selected
        if self.backup_driver_id:
            if self.backup_driver_id.id == self.driver_id.id:
                raise ValidationError(_("Primary driver and backup driver cannot be the same person."))
            b_ok, b_msg = self.backup_driver_id.check_availability(req.required_date, req.return_date)
            if not b_ok:
                raise ValidationError(_("Backup Driver Assignment Error: %s") % b_msg)

        # Emergency bypass handling (Section 9)
        post_trip = False
        if req.priority == 'emergency' and req.state in ['draft', 'submitted', 'under_review']:
            post_trip = True

        # Create Trip record (Section 14)
        trip_vals = {
            'request_id': req.id,
            'vehicle_id': self.vehicle_id.id,
            'driver_id': self.driver_id.id,
            'backup_driver_id': self.backup_driver_id.id if self.backup_driver_id else False,
            'trip_coordinator_id': self.trip_coordinator_id.id if self.trip_coordinator_id else self.env.user.id,
            'trip_type_id': self.trip_type_id.id if self.trip_type_id else False,
            'origin': req.origin,
            'destination': req.destination,
            'planned_departure': req.required_date,
            'planned_arrival': req.return_date,
            'planned_distance': self.planned_distance,
            'planned_duration': self.planned_duration,
            'purpose': req.purpose,
            'special_instructions': self.special_instructions,
            'state': 'ready',
        }
        trip = self.env['top.fleet.trip'].create(trip_vals)

        # Update Request status and metadata
        req_vals = {
            'assigned_vehicle_id': self.vehicle_id.id,
            'assigned_driver_id': self.driver_id.id,
            'trip_id': trip.id,
            'state': 'assigned',
            'post_trip_review_required': post_trip,
        }
        if req.state in ['draft', 'submitted', 'under_review']:
            req_vals['approved_by_id'] = self.env.user.id
            req_vals['approval_date'] = fields.Datetime.now()

        req.write(req_vals)

        # Update resource statuses
        self.vehicle_id.write({'operational_status': 'assigned'})
        self.driver_id.write({'driver_status': 'assigned'})
        if self.backup_driver_id:
            self.backup_driver_id.write({'driver_status': 'assigned'})

        req.message_post(
            body=_("Vehicle <strong>%s</strong> and Driver <strong>%s</strong> assigned. Trip generated: <a href='#' data-oe-model='top.fleet.trip' data-oe-id='%s'>%s</a>") % (
                self.vehicle_id.name, self.driver_id.name, trip.id, trip.name
            )
        )

        # Section 50: Send "Vehicle Assigned" notification
        template_assigned = self.env.ref('top_logistics_fleet.mail_template_vehicle_assigned', raise_if_not_found=False)
        if template_assigned:
            template_assigned.send_mail(req.id, force_send=False)

        activity_assigned = self.env.ref('top_logistics_fleet.mail_act_vehicle_assigned', raise_if_not_found=False)
        if activity_assigned and req.requester_id:
            req.activity_schedule(
                'top_logistics_fleet.mail_act_vehicle_assigned',
                summary=_("Vehicle %s and Driver %s Assigned to Request %s") % (self.vehicle_id.name, self.driver_id.name, req.name),
                user_id=req.requester_id.id,
            )

        return {
            'name': _('Trip Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.fleet.trip',
            'res_id': trip.id,
            'view_mode': 'form',
            'target': 'current',
        }
