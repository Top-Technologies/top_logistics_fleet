# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class GPSFuelTransaction(models.Model):
    _name = 'top.gps.fuel.transaction'
    _description = 'GPS Telematics Fuel Transaction (Refuel & Drain)'
    _order = 'timestamp desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Transaction ID', required=True, copy=False, default=lambda self: _('New'))
    transaction_type = fields.Selection([
        ('refuel', 'Fuel Refill'),
        ('drain', 'Abnormal Fuel Drain / Theft Alert'),
    ], string='Event Type', required=True, tracking=True, index=True)

    timestamp = fields.Datetime(string='Date & Time', required=True, tracking=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, tracking=True, index=True)
    license_plate = fields.Char(related='vehicle_id.license_plate', string='License Plate', readonly=True)
    device_id = fields.Many2one('top.gps.device', string='GPS Device', tracking=True)
    driver_id = fields.Many2one('hr.employee', string='Assigned Driver', domain="[('is_driver', '=', True)]")
    trip_id = fields.Many2one('top.fleet.trip', string='Associated Trip', index=True)

    initial_fuel = fields.Float(string='Starting Fuel Level (L)', digits=(10, 2), tracking=True)
    final_fuel = fields.Float(string='Ending Fuel Level (L)', digits=(10, 2), tracking=True)
    volume = fields.Float(string='Volume Changed (L)', digits=(10, 2), required=True, tracking=True)
    
    odometer = fields.Float(string='Odometer (km)', digits=(10, 1))
    speed = fields.Float(string='Vehicle Speed (km/h)')
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    address = fields.Char(string='Location / Address')

    state = fields.Selection([
        ('detected', 'GPS Detected'),
        ('verified', 'Verified / Approved'),
        ('flagged', 'Flagged for Audit'),
        ('dismissed', 'Dismissed / False Alarm'),
    ], string='Audit Status', default='detected', tracking=True, index=True)

    notes = fields.Text(string='Auditor Notes / Comments')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                prefix = 'REF' if vals.get('transaction_type') == 'refuel' else 'DRN'
                seq = self.env['ir.sequence'].next_by_code('top.gps.fuel.transaction')
                if not seq:
                    seq = f"{prefix}-{fields.Date.today().strftime('%Y%m%d')}-{self.search_count([]) + 1:04d}"
                vals['name'] = seq
        return super().create(vals_list)

    def action_verify(self):
        self.write({'state': 'verified'})

    def action_flag(self):
        self.write({'state': 'flagged'})

    def action_dismiss(self):
        self.write({'state': 'dismissed'})
