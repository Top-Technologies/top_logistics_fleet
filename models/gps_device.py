from odoo import fields, models


class GPSDevice(models.Model):
    _name = 'top.gps.device'
    _description = 'GPS Device Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name, id desc'

    name = fields.Char(string='Device Name', required=True, tracking=True)
    device_id = fields.Char(string='Device ID', required=True, copy=False, tracking=True, index=True)
    imei = fields.Char(string='IMEI', copy=False, tracking=True, index=True)
    sim_number = fields.Char(string='SIM Number', copy=False)
    provider_id = fields.Many2one('top.gps.provider', string='GPS API Provider', tracking=True)
    provider = fields.Selection([
        ('wialon', 'Wialon'),
        ('teltonika', 'Teltonika'),
        ('concox', 'Concox'),
        ('ruptela', 'Ruptela'),
        ('generic', 'Generic GPS API'),
    ], string='Provider Protocol', default='wialon', tracking=True)

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Assigned Vehicle',
        tracking=True,
        index=True,
    )
    installation_date = fields.Date(string='Installation Date')
    status = fields.Selection([
        ('active', 'Active'),
        ('offline', 'Offline'),
        ('suspended', 'Suspended'),
        ('faulty', 'Faulty'),
        ('unassigned', 'Unassigned'),
    ], string='Device Status', default='unassigned', tracking=True, index=True)

    # Real-time Telemetry Data (Sections 20, 21, 25)
    last_communication = fields.Datetime(string='Last Communication', tracking=True)
    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))
    address = fields.Char(string='Current Address / Geocoded Location')
    speed = fields.Float(string='Speed (km/h)')
    direction = fields.Float(string='Direction (°)')
    ignition = fields.Boolean(string='Ignition ON')
    odometer = fields.Float(string='Odometer (km)')
    fuel_level = fields.Float(string='Fuel Level (L)', digits=(10, 2), tracking=True)
    battery = fields.Float(string='Battery (V)')
    altitude = fields.Float(string='Altitude (m)')
    gps_signal = fields.Integer(string='GPS Satellites / Signal', default=100)
    last_sync = fields.Datetime(string='Last Synchronized')

    _sql_constraints = [
        ('device_id_unique', 'unique(device_id)', 'The GPS Device ID must be unique!'),
        ('imei_unique', 'unique(imei)', 'The Device IMEI must be unique!')
    ]

    @models.api.model
    def cron_check_offline_devices(self):
        """Section 50 & 53: Periodic scan for offline GPS tracking devices."""
        from datetime import timedelta
        config = self.env['top.fleet.alert.config'].get_active_config()
        if not config.alert_on_gps_offline:
            return

        minutes = config.offline_threshold_minutes or 30
        threshold = fields.Datetime.now() - timedelta(minutes=minutes)
        offline_devices = self.search([
            ('status', '=', 'active'),
            ('last_communication', '<', threshold),
        ])
        operator_group = self.env.ref('top_logistics_fleet.group_gps_operator', raise_if_not_found=False)
        target_user = operator_group.users[0] if operator_group and operator_group.users else self.env.user
        activity_type = self.env.ref('top_logistics_fleet.mail_act_gps_offline', raise_if_not_found=False)
        template = self.env.ref('top_logistics_fleet.mail_template_gps_offline', raise_if_not_found=False)

        for device in offline_devices:
            device.write({'status': 'offline'})
            if activity_type:
                existing = self.env['mail.activity'].search([
                    ('res_model', '=', 'top.gps.device'),
                    ('res_id', '=', device.id),
                    ('activity_type_id', '=', activity_type.id),
                ], limit=1)
                if not existing:
                    device.activity_schedule(
                        'top_logistics_fleet.mail_act_gps_offline',
                        summary=f"Vehicle GPS Offline: {device.vehicle_id.name or device.name}",
                        user_id=target_user.id,
                    )
            if template:
                template.send_mail(device.id, force_send=False)

