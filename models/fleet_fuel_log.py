from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class FleetFuelLog(models.Model):
    _name = 'top.fleet.fuel.log'
    _description = 'Vehicle Fuel Transaction Log'
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', readonly=True, default=lambda self: _('New'))
    date = fields.Datetime(string='Date & Time', default=fields.Datetime.now, required=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, index=True)
    driver_id = fields.Many2one('hr.employee', string='Driver', domain="[('is_driver', '=', True)]")
    trip_id = fields.Many2one('top.fleet.trip', string='Associated Trip', index=True)
    odometer = fields.Float(string='Odometer at Refuel (km)', required=True)
    fuel_station = fields.Char(string='Fuel Station / Location', required=True)
    fuel_type = fields.Selection([
        ('diesel', 'Diesel'),
        ('petrol_regular', 'Petrol (Regular)'),
        ('petrol_super', 'Petrol (Super)'),
        ('cng', 'CNG'),
        ('electric', 'Electric Recharge (kWh)'),
    ], string='Fuel Type', default='diesel', required=True)

    quantity = fields.Float(string='Quantity (Litres)', required=True)
    unit_price = fields.Float(string='Unit Price', required=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)

    payment_method = fields.Selection([
        ('fuel_card', 'Company Fuel Card'),
        ('cash', 'Petty Cash / Reimbursement'),
        ('voucher', 'Fuel Coupon / Voucher'),
        ('company_account', 'Direct Invoiced Account'),
    ], string='Payment Method', default='fuel_card', required=True)

    receipt = fields.Binary(string='Receipt Attachment', attachment=True)
    receipt_filename = fields.Char(string='Receipt Filename')
    notes = fields.Text(string='Notes / Station Remarks')

    @api.depends('quantity', 'unit_price')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = round(rec.quantity * rec.unit_price, 2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('top.fleet.fuel.log') or _('FUEL')
        return super().create(vals_list)
