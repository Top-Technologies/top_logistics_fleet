from datetime import timedelta
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_driver = fields.Boolean(string='Is Driver', default=False, tracking=True)
    driver_license_number = fields.Char(string='Driving License Number', tracking=True)
    license_category = fields.Selection([
        ('cat_1', 'Category 1 / Motorcycle'),
        ('cat_2', 'Category 2 / Light Automobile'),
        ('cat_3', 'Category 3 / Commercial Pickup & Van'),
        ('cat_4', 'Category 4 / Medium Truck & Bus'),
        ('cat_5', 'Category 5 / Heavy Truck & Trailer'),
        ('special', 'Special Machinery & Equipment'),
    ], string='License Category', tracking=True)
    license_issue_date = fields.Date(string='License Issue Date')
    license_expiry_date = fields.Date(string='License Expiry Date', tracking=True)
    emergency_contact = fields.Char(string='Emergency Contact Name')
    emergency_contact_phone = fields.Char(string='Emergency Contact Phone')
    driver_assigned_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Default Assigned Vehicle',
        tracking=True,
    )
    driver_status = fields.Selection([
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('on_trip', 'On Trip'),
        ('leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('inactive', 'Inactive'),
    ], string='Driver Status', default='available', tracking=True, index=True)

    is_license_expired = fields.Boolean(
        string='Is License Expired',
        compute='_compute_license_compliance',
        store=True,
    )
    license_compliance_status = fields.Char(
        string='License Status',
        compute='_compute_license_compliance',
        store=True,
    )

    @api.depends('license_expiry_date')
    def _compute_license_compliance(self):
        today = fields.Date.today()
        for emp in self:
            if emp.license_expiry_date and emp.license_expiry_date < today:
                emp.is_license_expired = True
                emp.license_compliance_status = _("License Expired on %s") % emp.license_expiry_date
            else:
                emp.is_license_expired = False
                emp.license_compliance_status = _("Valid License")

    @api.model
    def cron_check_driver_license_alerts(self):
        """Section 50 & 53: Daily scan for expiring driver licenses."""
        today = fields.Date.today()
        warning_window = today + timedelta(days=30)
        drivers = self.search([('is_driver', '=', True), ('active', '=', True)])
        officer_group = self.env.ref('top_logistics_fleet.group_fleet_officer', raise_if_not_found=False)
        officer_user = officer_group.users[0] if officer_group and officer_group.users else self.env.user

        for d in drivers:
            if d.license_expiry_date and d.license_expiry_date <= warning_window:
                d.activity_schedule(
                    'top_logistics_fleet.mail_act_license_expiring',
                    summary=_("Driver License Expiring Soon for %s (%s)") % (d.name, d.license_expiry_date),
                    user_id=officer_user.id,
                )

    def check_availability(self, start_date, end_date, exclude_trip_id=None):
        """Validates if driver is active, has a valid non-expired license, and has no overlapping trips."""
        self.ensure_one()
        today = fields.Date.today()

        if not self.active or self.driver_status in ['leave', 'suspended', 'inactive']:
            return False, _("Driver %s is currently inactive or on leave/suspended.") % self.name

        if self.license_expiry_date and self.license_expiry_date < today:
            return False, _("Driver %s driving license expired on %s.") % (self.name, self.license_expiry_date)

        domain = [
            ('driver_id', '=', self.id),
            ('state', 'in', ['ready', 'dispatched', 'in_transit']),
            ('planned_departure', '<', end_date),
            ('planned_arrival', '>', start_date),
        ]
        if exclude_trip_id:
            domain.append(('id', '!=', exclude_trip_id))

        overlapping = self.env['top.fleet.trip'].search(domain, limit=1)
        if overlapping:
            return False, _("Driver %s is already assigned to trip %s during this time window.") % (
                self.name, overlapping.name
            )

        return True, _("Available")
