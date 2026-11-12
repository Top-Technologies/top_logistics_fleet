# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    transport_request_ids = fields.One2many(
        'top.transport.request',
        'approval_request_id',
        string='Transport Requests',
        help='Linked transport requests governed by this approval request.',
    )
    transport_request_count = fields.Integer(
        string='Transport Requests Count',
        compute='_compute_transport_request_count',
    )

    @api.depends('transport_request_ids')
    def _compute_transport_request_count(self):
        for rec in self:
            rec.transport_request_count = len(rec.transport_request_ids)

    def action_approve(self, approver=None):
        """
        When the approval request is approved in the Approvals module,
        automatically approve linked transport requests if they are in submitted/under_review state.
        """
        res = super().action_approve(approver=approver)
        for req in self:
            if req.request_status == 'approved':
                pending_requests = req.transport_request_ids.filtered(
                    lambda tr: tr.state in ['submitted', 'under_review']
                )
                for tr in pending_requests:
                    try:
                        tr.write({
                            'state': 'approved',
                            'approved_by_id': self.env.user.id,
                            'approval_date': fields.Datetime.now(),
                        })
                        tr.message_post(
                            body=_("Transport request automatically approved via Approvals Module (Ref: %s).") % req.name,
                            message_type='notification',
                        )
                    except Exception as e:
                        _logger.warning("Could not auto-approve transport request %s: %s", tr.id, e)
        return res

    def action_refuse(self, approver=None):
        """
        When the approval request is refused in the Approvals module,
        automatically reject linked transport requests if they are submitted/under_review.
        """
        res = super().action_refuse(approver=approver)
        for req in self:
            if req.request_status == 'refused':
                pending_requests = req.transport_request_ids.filtered(
                    lambda tr: tr.state in ['submitted', 'under_review']
                )
                for tr in pending_requests:
                    try:
                        tr.write({
                            'state': 'rejected',
                            'rejection_reason': _("Refused via Approvals Module (%s)") % req.name,
                        })
                        tr.message_post(
                            body=_("Transport request rejected via Approvals Module (Ref: %s).") % req.name,
                            message_type='notification',
                        )
                    except Exception as e:
                        _logger.warning("Could not auto-refuse transport request %s: %s", tr.id, e)
        return res
