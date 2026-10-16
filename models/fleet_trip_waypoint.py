from odoo import fields, models


class FleetTripWaypoint(models.Model):
    _name = 'top.fleet.trip.waypoint'
    _description = 'Fleet Trip Waypoint / Intermediate Stop'
    _order = 'trip_id, sequence, id'

    trip_id = fields.Many2one(
        'top.fleet.trip',
        string='Trip',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Stop Order', default=10)
    location_name = fields.Char(string='Location / Stop Name', required=True)
    estimated_arrival = fields.Datetime(string='Estimated Arrival')
    actual_arrival = fields.Datetime(string='Actual Arrival')
    notes = fields.Char(string='Instructions / Activity')
    completed = fields.Boolean(string='Stop Visited', default=False)
