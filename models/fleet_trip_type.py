from odoo import fields, models


class FleetTripType(models.Model):
    _name = 'top.fleet.trip.type'
    _description = 'Fleet Trip Type'
    _order = 'sequence, name'

    name = fields.Char(string='Trip Type', required=True, translate=True)
    code = fields.Char(string='Code', required=True, copy=False)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The trip type code must be unique!')
    ]
