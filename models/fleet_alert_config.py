from odoo import api, fields, models, _


class FleetAlertConfig(models.Model):
    _name = 'top.fleet.alert.config'
    _description = 'Fleet Automatic Alert & Threshold Configuration (Section 53)'

    name = fields.Char(string='Rule Name', default='Fleet Safety & Alert Parameters', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)

    # Telemetry Alerts (Section 53)
    overspeed_threshold_kmh = fields.Float(string='Overspeed Threshold (km/h)', default=80.0)
    max_idling_minutes = fields.Float(string='Excessive Idling Threshold (Minutes)', default=15.0)
    alert_on_gps_offline = fields.Boolean(string='Alert on GPS Device Offline', default=True)
    offline_threshold_minutes = fields.Integer(string='GPS Offline Threshold (Minutes)', default=30)
    alert_on_geofence = fields.Boolean(string='Alert on Geofence Entry / Exit', default=True)
    alert_on_route_deviation = fields.Boolean(string='Alert on Route Deviation', default=True)
    alert_on_unauthorized_movement = fields.Boolean(string='Alert on Movement Outside Working Hours', default=True)

    # Document & Compliance Warning Windows (Section 53)
    license_expiry_warning_days = fields.Integer(string='Driver License Warning (Days before Expiry)', default=30)
    insurance_expiry_warning_days = fields.Integer(string='Insurance Warning (Days before Expiry)', default=30)
    registration_expiry_warning_days = fields.Integer(string='Registration Warning (Days before Expiry)', default=30)

    # Map Provider Setting (Section 52)
    mapping_provider = fields.Selection([
        ('osm', 'OpenStreetMap / Leaflet'),
        ('google', 'Google Maps'),
    ], string='Map Interface Provider', default='google', required=True)

    @api.model
    def get_active_config(self):
        config = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.create({'name': 'Default Fleet Parameters'})
        return config
