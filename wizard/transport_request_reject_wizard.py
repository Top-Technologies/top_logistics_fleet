from odoo import fields, models, _
from odoo.exceptions import UserError


class TransportRequestRejectWizard(models.TransientModel):
    _name = 'top.transport.request.reject.wizard'
    _description = 'Reject Transport Request Wizard'

    request_id = fields.Many2one(
        'top.transport.request',
        string='Transport Request',
        required=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        required=True,
    )

    def action_confirm_rejection(self):
        self.ensure_one()
        if not self.request_id:
            raise UserError(_("No transport request selected."))
        self.request_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason,
        })
        self.request_id.message_post(
            body=_("<strong>Request Rejected</strong> by %s.<br/><strong>Reason:</strong> %s") % (
                self.env.user.name, self.rejection_reason
            )
        )
        return {'type': 'ir.actions.act_window_close'}
