# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Anil Jangra
"""Sealing posted invoices and bills.

The order is the recorders' (docs/recorders.md): the record and its salt are saved in Odoo, and
committed, before the digest is sent, so an outage or a crash never loses one; the next run sends
it. An invoice is marked sealed only from the log's own answer for that digest (CLAUDE.md rule 5),
and posting an invoice never waits on the log or fails because of it.
"""
import base64
import hashlib
import json
import logging
import secrets

from odoo import _, api, fields, models

from ..lib import invoice_record, log_client
from ..lib.riskrouter_recorder import BUNDLE_FORMAT, record_digest

_logger = logging.getLogger(__name__)

ISSUED = ("out_invoice", "out_refund")
RECEIVED = ("in_invoice", "in_refund")
PER_RUN = 50
DEFAULT_API = "https://api.riskrouter.eu"


class AccountMove(models.Model):
    _inherit = "account.move"

    riskrouter_state = fields.Selection(
        [("pending", "Waiting for the log"), ("sealed", "Sealed"), ("refused", "Refused by the log")],
        string="Evidence seal", copy=False, readonly=True, index=True)
    riskrouter_record = fields.Text("Sealed record", copy=False, readonly=True, groups="account.group_account_manager")
    riskrouter_salt = fields.Char("Salt", copy=False, readonly=True, groups="account.group_account_manager")
    riskrouter_digest = fields.Char("Record digest", copy=False, readonly=True)
    riskrouter_leaf_index = fields.Integer("Leaf index", copy=False, readonly=True)
    riskrouter_sealed_at = fields.Char("Sealed at (log time)", copy=False, readonly=True)
    riskrouter_message = fields.Char("Last answer", copy=False, readonly=True)
    riskrouter_receipt_id = fields.Many2one("ir.attachment", "Receipt", copy=False, readonly=True)

    # ------------------------------------------------------------------ settings

    @api.model
    def _riskrouter_settings(self):
        get = self.env["ir.config_parameter"].sudo().get_param
        return {
            "key": (get("riskrouter_seal.api_key") or "").strip(),
            "api": (get("riskrouter_seal.api_base") or DEFAULT_API).strip().rstrip("/"),
            "issued": get("riskrouter_seal.seal_issued") == "True",
            "received": get("riskrouter_seal.seal_received", "False") == "True",
            "since": get("riskrouter_seal.since") or "",
        }

    def _riskrouter_types(self, settings):
        return (ISSUED if settings["issued"] else ()) + (RECEIVED if settings["received"] else ())

    # ------------------------------------------------------------------ the record

    def _riskrouter_document(self):
        """The file this record names: the issued invoice's PDF, or the bill's main attachment."""
        self.ensure_one()
        if self.move_type in ISSUED:
            return self.invoice_pdf_report_id
        return self.message_main_attachment_id

    def _riskrouter_build(self):
        """The pack record for this move, or raise ValueError saying what is missing."""
        self.ensure_one()
        doc = self._riskrouter_document().sudo()
        if not doc or not doc.raw:
            raise ValueError(_("there is no invoice file yet (send or print the invoice, or attach the bill)"))
        file_sha256 = hashlib.sha256(doc.raw).hexdigest()
        partner = self.commercial_partner_id.id or None
        if self.move_type in ISSUED:
            if not self.invoice_date:
                raise ValueError(_("the invoice has no date"))
            return invoice_record.issued_record(
                self.id, self.name, self.invoice_date.isoformat(), file_sha256, doc.mimetype, doc.name,
                partner_id=partner, origin=self.invoice_origin)
        received = doc.create_date.strftime("%Y-%m-%dT%H:%M:%SZ")  # Odoo stores datetimes in UTC
        return invoice_record.received_record(
            self.id, self.ref, received, file_sha256, doc.mimetype, doc.name, partner_id=partner)

    def _riskrouter_prepare(self):
        """Save the record and its salt on each move that has none yet. Nothing is sent here."""
        for move in self:
            if move.riskrouter_digest or move.riskrouter_state == "refused":
                continue
            try:
                record = move._riskrouter_build()
            except ValueError as e:
                move.sudo().riskrouter_message = str(e)
                continue
            salt = secrets.token_hex(32)
            move.sudo().write({
                "riskrouter_record": json.dumps(record, sort_keys=True),
                "riskrouter_salt": salt,
                "riskrouter_digest": record_digest(salt, record),
                "riskrouter_state": "pending",
                "riskrouter_message": _("Saved; waiting to be sent to the log."),
            })

    # ------------------------------------------------------------------ sending

    def _riskrouter_send(self, settings):
        """Send each pending digest. Returns how many were sealed."""
        sealed = 0
        for move in self:
            m = move.sudo()
            if m.riskrouter_state != "pending" or not m.riskrouter_digest:
                continue
            record = json.loads(m.riskrouter_record)
            outcome, entry, message = log_client.record(settings["api"], settings["key"], m.riskrouter_digest, record["kind"])
            if outcome == "sealed":
                m.write({
                    "riskrouter_state": "sealed",
                    "riskrouter_leaf_index": entry["leaf_index"],
                    "riskrouter_sealed_at": entry.get("created_at") or "",
                    "riskrouter_message": _("Sealed by the log as leaf %s.", entry["leaf_index"]),
                })
                m._riskrouter_attach_receipt(settings)
                sealed += 1
            elif outcome == "refused":
                m.write({"riskrouter_state": "refused", "riskrouter_message": message})
            else:
                m.write({"riskrouter_message": message})
            self.env.cr.commit()
        return sealed

    def _riskrouter_attach_receipt(self, settings):
        """Attach the receipt (riskrouter-record-bundle|1) once the proof can be had. Until then the
        move is sealed but has no receipt, and the next run tries again."""
        self.ensure_one()
        if self.riskrouter_receipt_id or self.riskrouter_state != "sealed":
            return
        proof = log_client.proof(settings["api"], settings["key"], self.riskrouter_leaf_index)
        if not proof:
            return
        bundle = {"format": BUNDLE_FORMAT, "record": json.loads(self.riskrouter_record),
                  "salt_hex": self.riskrouter_salt, "proof": proof}
        attachment = self.env["ir.attachment"].sudo().create({
            "name": "%s.riskrouter.json" % (self.name or "move-%d" % self.id).replace("/", "-"),
            "res_model": "account.move", "res_id": self.id, "mimetype": "application/json",
            "datas": base64.b64encode(json.dumps(bundle, indent=2, sort_keys=True).encode("utf-8")),
        })
        self.riskrouter_receipt_id = attachment.id

    # ------------------------------------------------------------------ entry points

    @api.model
    def _cron_riskrouter_seal(self):
        settings = self._riskrouter_settings()
        if not settings["key"]:
            _logger.info("RiskRouter: no API key set, nothing sealed")
            return
        if not settings["since"]:
            # From the day the module was configured, never every invoice ever posted.
            settings["since"] = fields.Date.today().isoformat()
            self.env["ir.config_parameter"].sudo().set_param("riskrouter_seal.since", settings["since"])
        types = self._riskrouter_types(settings)
        if not types:
            return
        domain = [("state", "=", "posted"), ("move_type", "in", types), ("invoice_date", ">=", settings["since"]),
                  ("riskrouter_state", "in", (False, "pending"))]
        moves = self.sudo().search(domain, order="id", limit=PER_RUN)
        moves._riskrouter_prepare()
        self.env.cr.commit()  # the record and its salt are kept before anything is sent
        moves.filtered(lambda m: m.riskrouter_state == "pending")._riskrouter_send(settings)
        # Receipts whose proof could not be had on the run that sealed them.
        for move in self.sudo().search([("riskrouter_state", "=", "sealed"), ("riskrouter_receipt_id", "=", False)], limit=PER_RUN):
            move._riskrouter_attach_receipt(settings)
            self.env.cr.commit()

    def action_riskrouter_seal_now(self):
        """Prepare the record now and ask the scheduled job to send it at once."""
        settings = self._riskrouter_settings()
        types = self._riskrouter_types(settings)
        self.filtered(lambda m: m.state == "posted" and m.move_type in types)._riskrouter_prepare()
        self.env.ref("riskrouter_seal.ir_cron_riskrouter_seal")._trigger()
        return True
