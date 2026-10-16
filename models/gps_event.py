from odoo import fields, models


class GPSEvent(models.Model):
    _name = 'top.gps.event'
    _description = 'GPS Automatic Telemetry Event'
    _order = 'timestamp desc, id desc'

    name = fields.Char(string='Event Description', required=True)
    event_type = fields.Selection([
        ('trip_start', 'Trip Start (Left Origin)'),
        ('trip_arrival', 'Trip Arrival (Entered Destination)'),
        ('overspeed', 'Overspeed Alert'),
        ('excessive_stop', 'Excessive Stop / Idling'),
        ('route_deviation', 'Route Deviation'),
        ('geofence_entry', 'Geofence Entry'),
        ('geofence_exit', 'Geofence Exit'),
        ('unauthorized_movement', 'Unauthorized Movement Outside Shift'),
        ('harsh_driving', 'Harsh Acceleration / Braking'),
    ], string='Event Type', required=True, index=True)

    severity = fields.Selection([
        ('info', 'Informational'),
        ('warning', 'Warning'),
        ('danger', 'Critical Violation'),
    ], string='Severity', default='info', required=True)

    trip_id = fields.Many2one('top.fleet.trip', string='Trip', ondelete='cascade', index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, index=True)
    driver_id = fields.Many2one('hr.employee', string='Driver', index=True)
    geofence_id = fields.Many2one('top.gps.geofence', string='Related Geofence')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True, index=True)
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    speed = fields.Float(string='Recorded Speed (km/h)')
    speed_limit = fields.Float(string='Threshold Speed (km/h)')
    duration_minutes = fields.Float(string='Duration (Minutes)')
    notes = fields.Text(string='Event Details')
