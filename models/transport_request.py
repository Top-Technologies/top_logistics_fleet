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
    origin = fields.Char(
        string='Origin',
        required=True,
    )
    destination = fields.Char(
        string='Destination',
        required=True,
    )
    passenger_count = fields.Integer(
        string='Passenger Count',
        default=1,
    )
    cargo_required = fields.Boolean(
        string='Cargo Required',
        default=False,
    )
    cargo_description = fields.Text(
        string='Cargo Description',
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
