from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FleetAccident(models.Model):
    _name = 'top.fleet.accident'
    _description = 'Fleet Accident & Incident Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Accident Reference',
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
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver at Time of Incident',
        domain="[('is_driver', '=', True)]",
        tracking=True,
        index=True,
    )
    trip_id = fields.Many2one(
        'top.fleet.trip',
        string='Associated Trip',
        tracking=True,
        index=True,
    )
    date = fields.Datetime(
        string='Incident Date & Time',
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True,
    )
    location = fields.Char(string='Incident Location', required=True)
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    description = fields.Text(string='Incident Description / Circumstances', required=True)
    damage_description = fields.Text(string='Observed Vehicle Damage', required=True)

    # Third Party
    third_party_involved = fields.Boolean(string='Third Party Involved', default=False)
    third_party_details = fields.Text(string='Third Party Vehicle / Contact Details')

    # Police & Legal
    police_report_filed = fields.Boolean(string='Police Report Filed', default=False)
    police_report_reference = fields.Char(string='Police Case / Station Reference')
    police_report_attachment = fields.Binary(string='Police Report Document', attachment=True)
    police_report_filename = fields.Char(string='Police Document Filename')

    # Insurance & Financials
    insurance_claim_filed = fields.Boolean(string='Insurance Claim Filed', default=False)
    insurance_claim_number = fields.Char(string='Insurance Claim Number', tracking=True)
    insurance_status = fields.Selection([
        ('not_claimed', 'Not Claimed'),
        ('submitted', 'Claim Submitted'),
        ('under_assessment', 'Under Assessor Review'),
        ('approved', 'Claim Approved'),
        ('settled', 'Claim Settled / Reimbursed'),
        ('rejected', 'Claim Rejected'),
    ], string='Insurance Status', default='not_claimed', tracking=True)

    estimated_cost = fields.Float(string='Estimated Repair Cost', tracking=True)
    actual_cost = fields.Float(string='Actual Settlement / Repair Cost', tracking=True)

    photo_ids = fields.Many2many(
        'ir.attachment',
        'fleet_accident_attachment_rel',
        'accident_id',
        'attachment_id',
        string='Damage Photos / Evidence',
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('reported', 'Reported'),
        ('under_investigation', 'Under Investigation'),
        ('insurance_claim', 'Insurance Claim'),
        ('resolved', 'Resolved & Repaired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', readonly=True, tracking=True, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('top.fleet.accident') or _('ACC')
        return super().create(vals_list)

    def action_report(self):
        for rec in self:
            rec.write({'state': 'reported'})
            rec.message_post(body=_("Accident officially reported."))

    def action_investigate(self):
        for rec in self:
            rec.write({'state': 'under_investigation'})
            rec.message_post(body=_("Accident investigation initiated."))

    def action_file_claim(self):
        for rec in self:
            rec.write({'state': 'insurance_claim', 'insurance_claim_filed': True})
            rec.message_post(body=_("Insurance claim initiated."))

    def action_resolve(self):
        for rec in self:
            rec.write({'state': 'resolved'})
            rec.message_post(body=_("Accident case resolved and closed."))

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})
            rec.message_post(body=_("Accident report cancelled."))

    def action_view_on_map(self):
        self.ensure_one()
        if not self.latitude or not self.longitude:
            raise UserError(_("No GPS coordinates recorded for this incident."))
        url = f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
