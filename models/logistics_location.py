# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class LogisticsLocation(models.Model):
    _name = 'top.logistics.location'
    _description = 'Predefined Logistics Location'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(
        string='Location Name',
        required=True,
        tracking=True,
        index=True,
    )
    code = fields.Char(
        string='Location Code',
        copy=False,
        tracking=True,
        index=True,
        help='Unique identifier e.g. HQ-ADD, BR-JIM, WHS-ADA',
    )
    location_type = fields.Selection([
        ('depot', 'Main Depot / Terminal'),
        ('branch', 'Branch Office'),
        ('farm', 'Farm Estate / Plantation'),
        ('warehouse', 'Warehouse / Hub'),
        ('project_site', 'Project / Field Site'),
        ('client', 'Client / Vendor Location'),
        ('transit', 'Transit / Fuel Stop'),
        ('other', 'Other Location'),
    ], string='Location Type', default='depot', required=True, tracking=True)

    contact_person = fields.Char(string='Contact Person')
    phone = fields.Char(string='Contact Phone')
    street = fields.Char(string='Street / Area Address')
    city = fields.Char(string='City / Town')
    state_id = fields.Many2one('res.country.state', string='Region / State')
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.ref('base.et', raise_if_not_found=False),
    )
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    geofence_id = fields.Many2one(
        'top.gps.geofence',
        string='Linked GPS Geofence',
        help='Optional GPS geofence linked to this location for automated arrival/departure detection.',
    )
    active = fields.Boolean(string='Active', default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    notes = fields.Text(string='Internal Notes / Instructions')

    def name_get(self):
        result = []
        for rec in self:
            label = f"[{rec.code}] {rec.name}" if rec.code else rec.name
            if rec.city:
                label += f" ({rec.city})"
            result.append((rec.id, label))
        return result

    @api.depends('name', 'code', 'city')
    def _compute_display_name(self):
        for rec in self:
            label = f"[{rec.code}] {rec.name}" if rec.code else rec.name
            if rec.city:
                label += f" ({rec.city})"
            rec.display_name = label

