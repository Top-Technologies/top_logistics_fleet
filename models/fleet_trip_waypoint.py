# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


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
    location_id = fields.Many2one(
        'top.logistics.location',
        string='Predefined Location',
    )
    location_name = fields.Char(string='Location / Stop Name', required=True)
    stop_type = fields.Selection([
        ('pickup', 'Passenger / Cargo Pickup'),
        ('delivery', 'Dropoff / Delivery'),
        ('waypoint', 'Intermediate Transit Stop'),
        ('rest', 'Rest / Fuel Stop'),
    ], string='Stop Purpose', default='waypoint', required=True)

    request_id = fields.Many2one(
        'top.transport.request',
        string='Linked Request',
        help='Specific transport request this stop belongs to if part of a consolidated multi-request order.',
    )
    cargo_or_passenger_notes = fields.Char(string='Passenger / Cargo Details')
    estimated_arrival = fields.Datetime(string='Estimated Arrival')
    actual_arrival = fields.Datetime(string='Actual Arrival')
    actual_departure = fields.Datetime(string='Actual Departure')
    odometer = fields.Float(string='Odometer at Stop (km)')
    time_spent_hours = fields.Float(
        string='Time Spent / Dwell (Hours)',
        compute='_compute_time_spent',
        store=True,
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('completed', 'Completed / Visited'),
        ('cancelled', 'Cancelled / Skipped'),
    ], string='Stop Status', default='pending')
    completed = fields.Boolean(
        string='Stop Visited',
        compute='_compute_completed',
        store=True,
        readonly=False,
    )
    notes = fields.Char(string='Instructions / Activity')

    @api.onchange('location_id')
    def _onchange_location_id(self):
        if self.location_id and not self.location_name:
            self.location_name = self.location_id.display_name or self.location_id.name

    @api.depends('state')
    def _compute_completed(self):
        for rec in self:
            rec.completed = (rec.state == 'completed')

    @api.onchange('completed')
    def _onchange_completed(self):
        for rec in self:
            if rec.completed and rec.state != 'completed':
                rec.state = 'completed'
                if not rec.actual_arrival:
                    rec.actual_arrival = fields.Datetime.now()
            elif not rec.completed and rec.state == 'completed':
                rec.state = 'pending'

    @api.depends('actual_arrival', 'actual_departure')
    def _compute_time_spent(self):
        for rec in self:
            if rec.actual_arrival and rec.actual_departure and rec.actual_departure > rec.actual_arrival:
                delta = rec.actual_departure - rec.actual_arrival
                rec.time_spent_hours = round(delta.total_seconds() / 3600.0, 2)
            else:
                rec.time_spent_hours = 0.0

    def action_mark_completed(self):
        now = fields.Datetime.now()
        for rec in self:
            vals = {'state': 'completed', 'completed': True}
            if not rec.actual_arrival:
                vals['actual_arrival'] = now
            if not rec.actual_departure:
                vals['actual_departure'] = now
            rec.write(vals)

    def action_cancel_stop(self):
        for rec in self:
            rec.write({'state': 'cancelled', 'completed': False})
