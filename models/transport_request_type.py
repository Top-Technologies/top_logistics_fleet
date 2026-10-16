from odoo import fields, models


class TransportRequestType(models.Model):
    _name = 'top.transport.request.type'
    _description = 'Transport Request Type'
    _order = 'sequence, name'

    name = fields.Char(string='Request Type', required=True, translate=True)
    code = fields.Char(string='Code', required=True, copy=False)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The request type code must be unique!')
    ]
