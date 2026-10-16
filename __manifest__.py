{
    'name': 'FMS Logistics & Fleet Management',
    'version': '18.0.1.3.0',
    'summary': 'End-to-end Transport Request, Vehicle & Driver Assignment, Trip Management, GPS Telematics, Accidents, and Cost Control',
    'description': """
FMS Logistics & Fleet Management
================================
Enterprise Logistics & Fleet Operations module covering the full lifecycle:
- Transport Request creation and multi-level approval workflows (Sections 1-9)
- Dynamic vehicle and driver availability checking with document compliance (Sections 10-12)
- Driver profile and license management (Section 13)
- Trip planning, execution, and intermediate waypoints (Sections 14-16)
- Pre-dispatch condition inspection checklist and vehicle release (Sections 17 & 35)
- GPS Device Master, API Providers, and standardized telemetry synchronization (Sections 18-26)
- Geofencing and automated trip events (Sections 27-28)
- Trip mileage, duration, and fuel reconciliation (Section 29)
- Fuel logging, consumption rate calculation (L/100km), and operating cost/km (Sections 30-32)
- Automated maintenance interval checks and service triggers (Section 33)
- Fleet Accident & Incident reporting with insurance and damage tracking (Section 34)
- Post-trip vehicle return inspection checklist with auto-incident creation (Section 36)
- Vehicle availability schedule calendar (Section 37)
- Dispatch pipeline board and executive logistics dashboard (Sections 38-39)
- Printable Trip Waybills and Vehicle Utilization PDF reports (Section 40)
- Role-based security (Requester, Approver, Fleet Officer, Fleet Manager, GPS Operator, Finance, Admin)
    """,
    'category': 'Operations/Fleet',
    'author': 'Top System Solutions & Technologies PLC',
    'website': 'https://www.topsystemsolutions.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'fleet',
        'hr',
        'mail',
        'maintenance',
        'web',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',

        # Data & Cron
        'data/ir_sequence_data.xml',
        'data/activity_types.xml',
        'data/mail_template.xml',
        'data/ir_cron_data.xml',
        'data/request_type_data.xml',
        'data/trip_type_data.xml',
        'data/master_data.xml',

        # Wizards
        'views/transport_request_reject_wizard_views.xml',
        'views/vehicle_assignment_wizard_views.xml',
        'views/fleet_dispatch_wizard_views.xml',
        'views/trip_return_wizard_views.xml',

        # Operational Views
        'views/transport_request_views.xml',
        'views/transport_request_type_views.xml',
        'views/fleet_trip_views.xml',
        'views/fleet_trip_type_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/hr_employee_views.xml',
        'views/fleet_fuel_log_views.xml',
        'views/fleet_fuel_analysis_views.xml',
        'views/gps_fuel_transaction_views.xml',
        'views/fuel_consumption_report_wizard_views.xml',
        'views/fleet_accident_views.xml',
        'views/dashboard_views.xml',

        # GPS & Telematics Views
        'views/gps_device_views.xml',
        'views/gps_provider_views.xml',
        'views/gps_geofence_views.xml',
        'views/gps_event_views.xml',
        'views/gps_position_views.xml',
        'views/fleet_map_views.xml',
        'views/alert_config_views.xml',

        # Menus
        'views/menus.xml',

        # Reports
        'reports/trip_report.xml',
        'reports/fleet_utilization.xml',
        'reports/fuel_report.xml',
        'reports/fleet_fuel_efficiency_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'top_logistics_fleet/static/src/css/logistics_dashboard.css',
            'top_logistics_fleet/static/src/css/vehicle_dashboard.css',
            'top_logistics_fleet/static/src/xml/logistics_dashboard.xml',
            'top_logistics_fleet/static/src/xml/vehicle_dashboard.xml',
            'top_logistics_fleet/static/src/js/logistics_dashboard.js',
            'top_logistics_fleet/static/src/js/vehicle_dashboard.js',
        ],
    },
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
