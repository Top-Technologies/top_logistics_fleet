from odoo import fields, models


class GPSGeofence(models.Model):
    _name = 'top.gps.geofence'
    _description = 'GPS Geofence Master'
    _order = 'name'

    name = fields.Char(string='Geofence Name', required=True)
    category = fields.Selection([
        ('office', 'Head Office / Branch'),
        ('warehouse', 'Warehouse / Depot'),
        ('project', 'Project Site'),
        ('customer', 'Customer Site'),
        ('fuel_station', 'Approved Fuel Station'),
        ('restricted', 'Restricted / No-Go Zone'),
        ('other', 'Other Zone'),
    ], string='Zone Category', required=True, default='office')

    geofence_type = fields.Selection([
        ('circle', 'Circular Radius'),
        ('polygon', 'Polygon Boundary'),
    ], string='Shape Type', default='circle', required=True)

    latitude = fields.Float(string='Center Latitude', digits=(10, 6), required=True)
    longitude = fields.Float(string='Center Longitude', digits=(10, 6), required=True)
    radius = fields.Float(string='Radius (Meters)', default=200.0, help='Radius in meters around coordinates')
    active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description / Restrictions')
    color = fields.Char(string='Display Color Hex', default='#3498db')
