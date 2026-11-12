from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TransportRequest(models.Model):
    _name = 'top.transport.request'
    _description = 'Transport Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Request Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
    )
    requester_id = fields.Many2one(
        'res.users',
        string='Requester',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Requester Employee',
        compute='_compute_employee_id',
        store=True,
        readonly=False,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        compute='_compute_department_id',
        store=True,
        readonly=False,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    request_date = fields.Datetime(
        string='Request Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    required_date = fields.Datetime(
        string='Required Date',
        required=True,
        tracking=True,
    )
    return_date = fields.Datetime(
        string='Return Date',
        required=True,
        tracking=True,
    )
    purpose = fields.Text(
        string='Purpose',
        required=True,
    )
    trip_type_id = fields.Many2one(
        'top.transport.request.type',
        string='Trip Type',
        required=True,
        tracking=True,
    )
    fleet_order_type_id = fields.Many2one(
        'approval.request',
        string='Fleet Order Type',
        tracking=True,
        help="Approval request from the Approvals module representing this fleet order approval subject.",
    )
    approver_ids = fields.One2many(
        'top.transport.request.approver',
        'request_id',
        string='Approvers',
        copy=True,
    )
    approvers_count = fields.Integer(
        string='Approvers Count',
        compute='_compute_approvers_summary',
        store=True,
    )
    pending_approvers_count = fields.Integer(
        string='Pending Approvals',
        compute='_compute_approvers_summary',
        store=True,
    )
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
    origin = fields.Char(
        string='Origin',
        required=True,
    )
    destination = fields.Char(
        string='Destination',
        required=True,
    )
    stop_ids = fields.One2many(
        'top.transport.request.stop',
        'request_id',
        string='Stops / Waypoints',
    )
    total_stops_count = fields.Integer(
        string='Total Stops Planned',
        compute='_compute_stops_summary',
        store=True,
    )
    completed_stops_count = fields.Integer(
        string='Stops Completed',
        compute='_compute_stops_summary',
        store=True,
    )
    cancelled_stops_count = fields.Integer(
        string='Stops Cancelled',
        compute='_compute_stops_summary',
        store=True,
    )
    passenger_count = fields.Integer(
        string='Passenger Count',
        default=1,
    )
    cargo_required = fields.Boolean(
        string='Cargo Required',
        default=False,
        tracking=True,
    )
    cargo_load_type = fields.Selection(
        [
            ('full', 'Full Load (ሙሉ ጭነት)'),
            ('empty', 'Empty Load (ባዶ ጭነት)'),
        ],
        string='Load Type',
        default='full',
        tracking=True,
    )
    cargo_product_id = fields.Many2one(
        'product.product',
        string='Loading Type / Product',
        tracking=True,
        help="Select or search the product / commodity being loaded and transported.",
    )
    cargo_loading_type_desc = fields.Char(
        string='Product / Commodity Description',
        tracking=True,
        help="Detailed name or description of the product/goods to be loaded.",
    )
    cargo_location_description = fields.Text(
        string='Location Description',
        tracking=True,
        help="Precise loading bay, warehouse gate, address, or offloading area details.",
    )
    cargo_approver_id = fields.Many2one(
        'res.users',
        string='Cargo Approver',
        default=lambda self: self.env.user,
        tracking=True,
        help="Supervisor or manager responsible for approving this cargo shipment.",
    )
    cargo_amount_qty = fields.Float(
        string='Amount In Quintal',
        digits='Product Unit of Measure',
        default=0.0,
        tracking=True,
        help="Amount or quantity of the cargo in Quintals (ኩንታል - 100 kg).",
    )
    cargo_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        default=lambda self: self.env.ref('top_logistics_fleet.uom_quintal', raise_if_not_found=False),
        tracking=True,
        help="Unit of measurement for the cargo amount (defaults to Quintal).",
    )
    cargo_tariff_unit_price = fields.Float(
        string='Tariff (Unit Price) / Quintal',
        digits='Product Price',
        default=0.0,
        tracking=True,
        help="Tariff or unit price per Quintal.",
    )
    cargo_currency_id = fields.Many2one(
        'res.currency',
        string='Tariff Currency',
        default=lambda self: self.env.company.currency_id,
    )
    cargo_total_tariff = fields.Monetary(
        string='Total Tariff Amount',
        currency_field='cargo_currency_id',
        compute='_compute_cargo_total_tariff',
        store=True,
        help="Computed total tariff amount (Amount Qty * Tariff Unit Price).",
    )
    cargo_load_capacity = fields.Float(
        string='Load Capacity',
        digits='Product Unit of Measure',
        default=0.0,
        tracking=True,
        help="Rated transport or vehicle load capacity for this cargo.",
    )
    cargo_capacity_uom_id = fields.Many2one(
        'uom.uom',
        string='Capacity UoM',
        tracking=True,
        help="Unit of measurement for the load capacity.",
    )
    cargo_description = fields.Text(
        string='Cargo / Handling Notes',
        help="Additional instructions regarding handling, weight, volume, or fragility.",
    )
    priority = fields.Selection(
        [
            ('low', 'Low'),
            ('normal', 'Normal'),
            ('high', 'High'),
            ('emergency', 'Emergency'),
        ],
        string='Priority',
        default='normal',
        required=True,
        tracking=True,
    )
    vehicle_type_id = fields.Many2one(
        'fleet.vehicle.model.category',
        string='Vehicle Type',
        tracking=True,
    )
    driver_required = fields.Boolean(
        string='Driver Required',
        default=True,
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('under_review', 'Under Review'),
            ('approved', 'Approved'),
            ('vehicle_search', 'Vehicle Search'),
            ('assigned', 'Assigned'),
            ('dispatched', 'Dispatched'),
            ('in_transit', 'In Transit'),
            ('completed', 'Completed'),
            ('reconciled', 'Reconciled'),
            ('closed', 'Closed'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        readonly=True,
        tracking=True,
        index=True,
        copy=False,
    )

    # Workflow & Approval Metadata (Section 9)
    reviewed_by_id = fields.Many2one(
        'res.users',
        string='Reviewed By',
        readonly=True,
        copy=False,
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        copy=False,
    )
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        copy=False,
    )
    post_trip_review_required = fields.Boolean(
        string='Post-Trip Review Required',
        default=False,
        help="Flagged when an emergency request bypasses standard approval for immediate assignment.",
    )

    # Assignment & Trip Linkage (Sections 10, 11, 14)
    assigned_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Assigned Vehicle',
        readonly=True,
        tracking=True,
        copy=False,
    )
    assigned_driver_id = fields.Many2one(
        'hr.employee',
        string='Assigned Driver',
        readonly=True,
        tracking=True,
        copy=False,
    )
    trip_id = fields.Many2one(
        'top.fleet.trip',
        string='Trip Record',
        readonly=True,
        copy=False,
    )
    trip_count = fields.Integer(
        string='Trip Count',
        compute='_compute_trip_count',
    )
    vehicle_last_service_date = fields.Date(
        related='assigned_vehicle_id.last_service_date',
        string='Vehicle Last Service Date',
        readonly=True,
    )
    vehicle_next_service_date = fields.Date(
        related='assigned_vehicle_id.next_service_date',
        string='Vehicle Next Service Due',
        readonly=True,
    )
    vehicle_service_status = fields.Selection(
        related='assigned_vehicle_id.service_status',
        string='Vehicle Service Status',
        readonly=True,
    )
    vehicle_is_service_due = fields.Boolean(
        related='assigned_vehicle_id.is_service_due',
        string='Maintenance Service Due Alert',
        readonly=True,
    )
    driver_license_expiry_date = fields.Date(
        related='assigned_driver_id.license_expiry_date',
        string='Driver License Expiration',
        readonly=True,
    )
    driver_is_license_expired = fields.Boolean(
        related='assigned_driver_id.is_license_expired',
        string='Driver License Expired',
        readonly=True,
    )
    driver_license_compliance = fields.Char(
        related='assigned_driver_id.license_compliance_status',
        string='Driver License Status',
        readonly=True,
    )
    trip_actual_distance = fields.Float(
        related='trip_id.actual_distance',
        string='Actual Distance (km)',
        readonly=True,
    )
    trip_actual_duration = fields.Float(
        related='trip_id.actual_duration',
        string='Actual Duration (Hours)',
        readonly=True,
    )
    trip_duration_display = fields.Char(
        string='Trip Duration Taken',
        compute='_compute_trip_duration_display',
    )

    @api.depends('approver_ids.status')
    def _compute_approvers_summary(self):
        for record in self:
            record.approvers_count = len(record.approver_ids)
            record.pending_approvers_count = len(record.approver_ids.filtered(lambda a: a.status == 'pending'))

    @api.onchange('fleet_order_type_id')
    def _onchange_fleet_order_type_id(self):
        if self.fleet_order_type_id:
            if not self.approver_ids and hasattr(self.fleet_order_type_id, 'approver_ids'):
                lines = []
                seq = 10
                for app_line in self.fleet_order_type_id.approver_ids:
                    st = 'approved' if getattr(app_line, 'status', '') == 'approved' else 'rejected' if getattr(app_line, 'status', '') == 'refused' else 'pending'
                    lines.append((0, 0, {
                        'user_id': app_line.user_id.id,
                        'role': getattr(app_line.user_id.partner_id, 'function', False) or _('Approver'),
                        'sequence': seq,
                        'status': st,
                    }))
                    seq += 10
                if lines:
                    self.approver_ids = lines
            if not self.purpose and hasattr(self.fleet_order_type_id, 'reason') and self.fleet_order_type_id.reason:
                self.purpose = self.fleet_order_type_id.reason
            if not self.required_date and hasattr(self.fleet_order_type_id, 'date_start') and self.fleet_order_type_id.date_start:
                self.required_date = self.fleet_order_type_id.date_start
            if not self.return_date and hasattr(self.fleet_order_type_id, 'date_end') and self.fleet_order_type_id.date_end:
                self.return_date = self.fleet_order_type_id.date_end
            if not self.destination and hasattr(self.fleet_order_type_id, 'location') and self.fleet_order_type_id.location:
                self.destination = self.fleet_order_type_id.location

    @api.onchange('origin_location_id')
    def _onchange_origin_location_id(self):
        if self.origin_location_id:
            self.origin = self.origin_location_id.display_name or self.origin_location_id.name

    @api.onchange('destination_location_id')
    def _onchange_destination_location_id(self):
        if self.destination_location_id:
            self.destination = self.destination_location_id.display_name or self.destination_location_id.name

    @api.depends('cargo_amount_qty', 'cargo_tariff_unit_price')
    def _compute_cargo_total_tariff(self):
        for rec in self:
            rec.cargo_total_tariff = (rec.cargo_amount_qty or 0.0) * (rec.cargo_tariff_unit_price or 0.0)

    @api.onchange('cargo_product_id')
    def _onchange_cargo_product_id(self):
        if self.cargo_product_id:
            if not self.cargo_loading_type_desc:
                self.cargo_loading_type_desc = self.cargo_product_id.display_name
            if self.cargo_product_id.uom_id:
                self.cargo_uom_id = self.cargo_product_id.uom_id
            elif not self.cargo_uom_id:
                quintal = self.env.ref('top_logistics_fleet.uom_quintal', raise_if_not_found=False)
                if quintal:
                    self.cargo_uom_id = quintal

    @api.onchange('assigned_vehicle_id')
    def _onchange_assigned_vehicle_capacity(self):
        if self.assigned_vehicle_id and hasattr(self.assigned_vehicle_id, 'capacity_cargo_kg') and self.assigned_vehicle_id.capacity_cargo_kg:
            if not self.cargo_load_capacity:
                self.cargo_load_capacity = self.assigned_vehicle_id.capacity_cargo_kg
            kg_uom = self.env.ref('uom.product_uom_kgm', raise_if_not_found=False)
            if kg_uom and not self.cargo_capacity_uom_id:
                self.cargo_capacity_uom_id = kg_uom.id

    @api.depends('stop_ids.state')
    def _compute_stops_summary(self):
        for record in self:
            record.total_stops_count = len(record.stop_ids)
            record.completed_stops_count = len(record.stop_ids.filtered(lambda s: s.state == 'completed'))
            record.cancelled_stops_count = len(record.stop_ids.filtered(lambda s: s.state == 'cancelled'))

    @api.depends('trip_id.actual_duration')
    def _compute_trip_duration_display(self):
        for record in self:
            if record.trip_id and record.trip_id.actual_duration:
                total_hours = record.trip_id.actual_duration
                hrs = int(total_hours)
                mins = int(round((total_hours - hrs) * 60))
                record.trip_duration_display = f"{hrs}h {mins}m"
            else:
                record.trip_duration_display = _("Not Recorded")

    @api.depends('trip_id')
    def _compute_trip_count(self):
        for record in self:
            record.trip_count = 1 if record.trip_id else 0

    @api.depends('requester_id')
    def _compute_employee_id(self):
        for record in self:
            employee = self.env['hr.employee'].search([
                ('user_id', '=', record.requester_id.id),
                ('company_id', '=', record.company_id.id),
            ], limit=1)
            record.employee_id = employee or False

    @api.depends('employee_id')
    def _compute_department_id(self):
        for record in self:
            if record.employee_id and record.employee_id.department_id:
                record.department_id = record.employee_id.department_id
            elif not record.department_id:
                record.department_id = False

    @api.constrains('required_date', 'return_date')
    def _check_dates(self):
        for record in self:
            if record.required_date and record.return_date and record.return_date < record.required_date:
                raise ValidationError(_("Return Date (%s) cannot be earlier than Required Date (%s).") % (
                    record.return_date, record.required_date
                ))

    @api.constrains('passenger_count')
    def _check_passenger_count(self):
        for record in self:
            if record.passenger_count < 0:
                raise ValidationError(_("Passenger Count cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('top.transport.request') or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # WORKFLOW ACTIONS
    # -------------------------------------------------------------------------
    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            record.write({'state': 'submitted'})
            if record.priority == 'emergency':
                record.message_post(
                    body=_("<strong>EMERGENCY Transport Request Submitted!</strong> Immediate Fleet assignment authorized with post-trip review."),
                    message_type='notification',
                )
            else:
                record.message_post(
                    body=_("Transport request submitted for approval."),
                    message_type='notification',
                )

            # Section 50: Send "Transport Request Submitted" notification
            template_submitted = self.env.ref('top_logistics_fleet.mail_template_transport_request_submitted', raise_if_not_found=False)
            if template_submitted:
                template_submitted.send_mail(record.id, force_send=False)

            # Section 50: Send "Transport Request Awaiting Approval" notification & schedule activity
            approver_user = False
            if record.department_id and record.department_id.manager_id and record.department_id.manager_id.user_id:
                approver_user = record.department_id.manager_id.user_id
            else:
                approver_group = self.env.ref('top_logistics_fleet.group_department_approver', raise_if_not_found=False)
                if approver_group and approver_group.users:
                    approver_user = approver_group.users[0]

            if approver_user:
                activity_type = self.env.ref('top_logistics_fleet.mail_act_request_awaiting_approval', raise_if_not_found=False)
                if activity_type:
                    record.activity_schedule(
                        'top_logistics_fleet.mail_act_request_awaiting_approval',
                        summary=_("Transport Request Awaiting Approval: %s") % record.name,
                        user_id=approver_user.id,
                    )
            
            template_awaiting = self.env.ref('top_logistics_fleet.mail_template_request_awaiting_approval', raise_if_not_found=False)
            if template_awaiting:
                template_awaiting.send_mail(record.id, force_send=False)

            # Also notify Fleet Supervisor
            supervisor_group = self.env.ref('top_logistics_fleet.group_fleet_supervisor', raise_if_not_found=False)
            supervisor_user = supervisor_group.users[0] if supervisor_group and supervisor_group.users else False
            if supervisor_user:
                activity_type = self.env.ref('top_logistics_fleet.mail_act_request_awaiting_approval', raise_if_not_found=False)
                if activity_type:
                    record.activity_schedule(
                        'top_logistics_fleet.mail_act_request_awaiting_approval',
                        summary=_("Transport Order Awaiting Fleet Supervisor Review: %s") % record.name,
                        user_id=supervisor_user.id,
                    )

            # Notify all assigned individual approvers
            activity_type = self.env.ref('top_logistics_fleet.mail_act_request_awaiting_approval', raise_if_not_found=False)
            for approver in record.approver_ids.filtered(lambda a: a.status == 'pending'):
                if activity_type and approver.user_id:
                    record.activity_schedule(
                        'top_logistics_fleet.mail_act_request_awaiting_approval',
                        summary=_("Transport Request Awaiting Your Approval: %s") % record.name,
                        user_id=approver.user_id.id,
                    )

    def action_review(self):
        for record in self:
            if record.state != 'submitted':
                raise UserError(_("Only submitted requests can be put under review."))
            record.write({
                'state': 'under_review',
                'reviewed_by_id': self.env.user.id,
            })
            record.message_post(body=_("Request reviewed by %s.") % self.env.user.name)

    def action_approve(self):
        for record in self:
            if record.state not in ['submitted', 'under_review']:
                raise UserError(_("Request cannot be approved in its current state."))
            # Mark current user's approver line as approved if present
            my_approver_lines = record.approver_ids.filtered(
                lambda a: a.user_id.id == self.env.user.id and a.status == 'pending'
            )
            if my_approver_lines:
                my_approver_lines.write({
                    'status': 'approved',
                    'action_date': fields.Datetime.now(),
                })
            record.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approval_date': fields.Datetime.now(),
            })
            record.message_post(body=_("Transport request approved by %s.") % self.env.user.name)

    def action_vehicle_search(self):
        for record in self:
            if record.state != 'approved':
                raise UserError(_("Vehicle search can only be initiated for approved requests."))
            record.write({'state': 'vehicle_search'})

    def action_open_assignment_wizard(self):
        """Opens vehicle and driver assignment wizard (Section 11)."""
        self.ensure_one()
        # In emergency mode, allows direct assignment
        context = {
            'default_request_id': self.id,
            'default_trip_type_id': self.trip_type_id.id if self.trip_type_id else False,
            'default_planned_distance': 0.0,
        }
        return {
            'name': _('Assign Vehicle & Driver'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.vehicle.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_view_trip(self):
        """Smart button action to view the generated trip."""
        self.ensure_one()
        if not self.trip_id:
            raise UserError(_("No trip has been created for this request yet."))
        return {
            'name': _('Trip Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'top.fleet.trip',
            'res_id': self.trip_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        for record in self:
            if record.state in ['in_transit', 'completed', 'reconciled', 'closed']:
                raise UserError(_("Cannot cancel a request that is already in transit or completed."))
            if record.trip_id and record.trip_id.state not in ['cancelled', 'draft']:
                record.trip_id.action_cancel()
            record.write({'state': 'cancelled'})
            record.message_post(body=_("Transport request cancelled."))

    def action_reset_draft(self):
        for record in self:
            if record.state not in ['cancelled', 'rejected']:
                raise UserError(_("Only cancelled or rejected requests can be reset to draft."))
            record.write({
                'state': 'draft',
                'rejection_reason': False,
            })
            record.message_post(body=_("Request reset to draft."))


class TransportRequestStop(models.Model):
    _name = 'top.transport.request.stop'
    _description = 'Transport Request Intermediate Stop / Waypoint'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one(
        'top.transport.request',
        string='Transport Request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    location_id = fields.Many2one(
        'top.logistics.location',
        string='Predefined Location',
    )
    location_name = fields.Char(string='Location / Stop Name', required=True)
    stop_type = fields.Selection([
        ('pickup', 'Passenger / Cargo Pickup'),
        ('delivery', 'Dropoff / Delivery'),
        ('waypoint', 'Intermediate Transit Stop'),
        ('rest', 'Rest / Fuel Stop'),
    ], string='Stop Purpose', default='waypoint', required=True)
    estimated_arrival = fields.Datetime(string='Estimated Arrival')
    actual_arrival = fields.Datetime(string='Actual Arrival')
    actual_departure = fields.Datetime(string='Actual Departure')
    cargo_or_passenger_notes = fields.Char(string='Passengers / Cargo Details')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled / Skipped'),
    ], string='Stop Status', default='pending')
    completed = fields.Boolean(
        string='Stop Visited',
        compute='_compute_completed',
        store=True,
        readonly=False,
    )
    notes = fields.Char(string='Notes / Instructions')

    @api.onchange('location_id')
    def _onchange_location_id(self):
        if self.location_id and not self.location_name:
            self.location_name = self.location_id.display_name or self.location_id.name

    @api.depends('state')
    def _compute_completed(self):
        for rec in self:
            rec.completed = (rec.state == 'completed')

    @api.onchange('completed')
    def _onchange_completed(self):
        for rec in self:
            if rec.completed and rec.state != 'completed':
                rec.state = 'completed'
                if not rec.actual_arrival:
                    rec.actual_arrival = fields.Datetime.now()
            elif not rec.completed and rec.state == 'completed':
                rec.state = 'pending'

    def action_mark_completed(self):
        now = fields.Datetime.now()
        for rec in self:
            vals = {'state': 'completed', 'completed': True}
            if not rec.actual_arrival:
                vals['actual_arrival'] = now
            if not rec.actual_departure:
                vals['actual_departure'] = now
            rec.write(vals)

    def action_cancel_stop(self):
        for rec in self:
            rec.write({'state': 'cancelled', 'completed': False})


class TransportRequestApprover(models.Model):
    _name = 'top.transport.request.approver'
    _description = 'Transport Request Approver'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    request_id = fields.Many2one(
        'top.transport.request',
        string='Transport Request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Approver',
        required=True,
        index=True,
    )
    role = fields.Char(
        string='Role / Designation',
        help="e.g. Department Manager, Fleet Supervisor, Cargo Manager, Operations Director",
    )
    status = fields.Selection(
        [
            ('pending', 'To Approve'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='pending',
        required=True,
    )
    action_date = fields.Datetime(
        string='Action Date',
        readonly=True,
    )
    comments = fields.Char(
        string='Comments / Reason',
    )

    def action_approve(self):
        for rec in self:
            rec.write({
                'status': 'approved',
                'action_date': fields.Datetime.now(),
            })
            rec.request_id.message_post(
                body=_("Approver <strong>%s</strong> (%s) approved the request.") % (
                    rec.user_id.name, rec.role or _("Approver")
                )
            )
            # If all approvers have approved, automatically advance request to approved
            all_approved = all(app.status == 'approved' for app in rec.request_id.approver_ids)
            if all_approved and rec.request_id.state in ['submitted', 'under_review']:
                rec.request_id.write({
                    'state': 'approved',
                    'approved_by_id': rec.user_id.id,
                    'approval_date': fields.Datetime.now(),
                })
                rec.request_id.message_post(
                    body=_("All required approvers have approved. Request status moved to <strong>Approved</strong>.")
                )

    def action_reject(self):
        for rec in self:
            rec.write({
                'status': 'rejected',
                'action_date': fields.Datetime.now(),
            })
            reason = rec.comments or _("Rejected by %s") % rec.user_id.name
            rec.request_id.message_post(
                body=_("Approver <strong>%s</strong> (%s) rejected the request. Reason: %s") % (
                    rec.user_id.name, rec.role or _("Approver"), reason
                )
            )
            if rec.request_id.state in ['submitted', 'under_review']:
                rec.request_id.write({
                    'state': 'rejected',
                    'rejection_reason': reason,
                })


