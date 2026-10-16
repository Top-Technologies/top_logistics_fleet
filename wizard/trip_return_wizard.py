from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TripReturnWizard(models.TransientModel):
    _name = 'top.trip.return.wizard'
    _description = 'Post-Trip Return Inspection Checklist Wizard (Section 36)'

    trip_id = fields.Many2one('top.fleet.trip', string='Trip', required=True)
    vehicle_id = fields.Many2one(related='trip_id.vehicle_id', string='Vehicle', readonly=True)
    driver_id = fields.Many2one(related='trip_id.driver_id', string='Driver', readonly=True)
    start_odometer = fields.Float(related='trip_id.start_odometer', string='Starting Odometer (km)', readonly=True)

    # Return checklist fields from Section 36
    vehicle_returned = fields.Boolean(string='Vehicle Physically Returned to Depot', default=True, required=True)
    end_odometer = fields.Float(string='Ending Odometer (km)', required=True)
    start_fuel = fields.Float(related='trip_id.start_fuel', string='Starting Fuel Level (L)', readonly=True)
    end_fuel = fields.Float(string='Ending Fuel Level (L)', required=True, default=0.0)
    fuel_consumed_preview = fields.Float(
        string='Calculated Consumption (L)',
        compute='_compute_fuel_preview',
        readonly=True,
        help='Estimated fuel consumed based on (Start Fuel + Trip Refuels) - End Fuel.',
    )
    end_fuel_level = fields.Selection([
        ('quarter', '1/4 Tank'),
        ('half', '1/2 Tank'),
        ('three_quarter', '3/4 Tank'),
        ('full', 'Full Tank'),
    ], string='Final Fuel Gauge Level', required=True, default='half')

    @api.depends('start_fuel', 'end_fuel', 'trip_id.total_refueled', 'trip_id.fuel_log_ids.quantity')
    def _compute_fuel_preview(self):
        for rec in self:
            refueled = sum(rec.trip_id.fuel_log_ids.mapped('quantity')) if rec.trip_id else 0.0
            if rec.start_fuel > 0.0 and rec.end_fuel > 0.0:
                rec.fuel_consumed_preview = max(0.0, round((rec.start_fuel + refueled) - rec.end_fuel, 2))
            else:
                rec.fuel_consumed_preview = 0.0

    cleanliness_status = fields.Selection([
        ('clean', 'Clean / Satisfactory'),
        ('acceptable', 'Normal Dust / Acceptable'),
        ('needs_wash', 'Dirty / Requires Wash'),
    ], string='Interior & Exterior Cleanliness', default='clean', required=True)

    has_damage = fields.Boolean(string='New Damage Identified', default=False)
    damage_description = fields.Text(string='Damage Description / Location on Body')
    damage_photo_ids = fields.Many2many(
        'ir.attachment',
        'trip_return_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='Damage Photos / Evidence (Section 51)',
    )
    missing_equipment = fields.Char(string='Missing Equipment / Tools (if any)')
    new_defects = fields.Text(string='New Mechanical / Electrical Defects')
    driver_comments = fields.Text(string='Driver Debrief & Trip Comments')

    @api.constrains('end_odometer')
    def _check_odometer(self):
        for rec in self:
            if rec.end_odometer < rec.start_odometer:
                raise ValidationError(_("Ending odometer (%s km) cannot be less than starting odometer (%s km).") % (
                    rec.end_odometer, rec.start_odometer
                ))

    def action_confirm_return(self):
        self.ensure_one()
        trip = self.trip_id
        now = fields.Datetime.now()
        dist = max(0.0, self.end_odometer - trip.start_odometer)

        # 1. Update Trip Record
        trip_vals = {
            'state': 'completed',
            'actual_arrival': now,
            'actual_distance': dist,
            'end_odometer': self.end_odometer,
            'end_fuel': self.end_fuel,
            'end_fuel_level': self.end_fuel_level,
            'vehicle_returned': self.vehicle_returned,
            'return_cleanliness': self.cleanliness_status,
            'has_damage': self.has_damage,
            'damage_description': self.damage_description,
            'missing_equipment': self.missing_equipment,
            'new_defects': self.new_defects,
            'driver_comments': self.driver_comments,
        }

        # 2. Update Vehicle Odometer
        trip.vehicle_id.write({
            'odometer': self.end_odometer,
            'operational_status': 'available',
        })
        trip.driver_id.write({'driver_status': 'available'})
        if trip.backup_driver_id:
            trip.backup_driver_id.write({'driver_status': 'available'})

        # 3. Handle Damage (Section 36: Auto-create incident & maintenance record)
        if self.has_damage:
            accident = self.env['top.fleet.accident'].create({
                'vehicle_id': trip.vehicle_id.id,
                'driver_id': trip.driver_id.id,
                'trip_id': trip.id,
                'date': now,
                'location': trip.destination,
                'description': _("Post-trip return inspection identified damage: %s") % (self.damage_description or _("Not specified")),
                'damage_description': self.damage_description or _("Defects observed upon return."),
                'photo_ids': [(6, 0, self.damage_photo_ids.ids)] if self.damage_photo_ids else False,
                'state': 'reported',
            })
            trip_vals['accident_id'] = accident.id
            trip.vehicle_id.write({'operational_status': 'maintenance'})

            # Create Maintenance Request
            maint_model = self.env.get('maintenance.request')
            if maint_model:
                maint_model.sudo().create({
                    'name': _("Post-Trip Repair: %s (%s)") % (trip.vehicle_id.name, trip.name),
                    'maintenance_type': 'corrective',
                    'description': _("Damage flagged on return inspection:\n%s\nDefects: %s") % (
                        self.damage_description, self.new_defects or 'None'
                    ),
                })

        trip.write(trip_vals)

        # 4. Check for high mileage service interval (Section 33)
        if trip.vehicle_id.is_service_due:
            trip.vehicle_id.trigger_service_maintenance_request()

        # 5. Advance Request Status
        if trip.request_id:
            trip.request_id.write({'state': 'completed'})
            trip.request_id.message_post(
                body=_("Vehicle returned from trip. Completed distance: <strong>%s km</strong>.") % dist
            )

        trip.message_post(
            body=_("Return inspection completed. Odometer: <strong>%s km</strong> (Travelled: %s km). Damage flagged: <strong>%s</strong>") % (
                self.end_odometer, dist, _('Yes') if self.has_damage else _('No')
            )
        )

        return {'type': 'ir.actions.act_window_close'}
