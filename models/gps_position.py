from odoo import fields, models


class GPSPosition(models.Model):
    _name = 'top.gps.position'
    _description = 'GPS Position Telemetry Log'
    _order = 'timestamp desc, id desc'

    device_id = fields.Many2one(
        'top.gps.device',
        string='GPS Device',
        required=True,
        ondelete='cascade',
        index=True,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        index=True,
    )
    trip_id = fields.Many2one(
        'top.fleet.trip',
        string='Trip',
        index=True,
        ondelete='set null',
    )
    timestamp = fields.Datetime(string='Timestamp', required=True, index=True)
    latitude = fields.Float(string='Latitude', digits=(10, 6), required=True)
    longitude = fields.Float(string='Longitude', digits=(10, 6), required=True)
    speed = fields.Float(string='Speed (km/h)')
    direction = fields.Float(string='Direction (°)')
    ignition = fields.Boolean(string='Ignition')
    odometer = fields.Float(string='Odometer (km)')
    engine_status = fields.Selection([
        ('running', 'Engine Running'),
        ('idling', 'Idling'),
        ('stopped', 'Engine Stopped'),
    ], string='Engine Status', default='running')
    gps_signal = fields.Integer(string='GPS Signal Strength (%)')
    battery = fields.Float(string='Battery Voltage (V)')
    fuel_level = fields.Float(string='Fuel Level (L)', digits=(10, 2))
    altitude = fields.Float(string='Altitude (m)')
    address = fields.Char(string='Location / Address')
