# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Anil Jangra
"""The records this module seals, built from plain values so they can be tested without Odoo.

Each record is a `vat-invoice` pack record (https://riskrouter.eu/packs/vat-invoice.json, version 1):
`invoice.issued` for a customer invoice or credit note, `invoice.received` for a vendor bill or refund.
The invoice file itself never leaves Odoo: the record names it by its SHA-256, and only the salted
digest of the record is sent to the log (CLAUDE.md rule 15).

References are the module's own ids (`odoo-partner-42`), never a name: the pack refuses names and
emails in reference fields, and nothing about a customer or a supplier is put in a record.
"""
import re

PACK = "vat-invoice"
PACK_VERSION = 1
REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
DIGEST = re.compile(r"^[0-9a-f]{64}\Z")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}\Z")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def reference(value):
    """A value as a pack reference: kept when it already is one, otherwise its invalid characters
    become hyphens. None when nothing usable is left."""
    if value is None:
        return None
    text = str(value).strip()
    if REFERENCE.match(text):
        return text
    text = re.sub(r"[^A-Za-z0-9._:/-]+", "-", text).strip("-._:/")[:128]
    return text if text and REFERENCE.match(text) else None


def invoice_format(mimetype, filename=""):
    """The pack's invoice_format for a file: a PDF is `pdf`; anything else is `other`, because the
    file alone does not say which e-invoicing syntax it follows."""
    name = (filename or "").lower()
    if mimetype == "application/pdf" or name.endswith(".pdf"):
        return "pdf"
    return "other"


def issued_record(move_id, invoice_number, invoice_date, file_sha256, mimetype, filename="", partner_id=None, origin=None):
    """An invoice.issued record for a posted customer invoice or credit note."""
    if not DIGEST.match(file_sha256 or ""):
        raise ValueError("the invoice file's SHA-256 is not a lowercase hex digest")
    if not DATE.match(invoice_date or ""):
        raise ValueError("the invoice date is not YYYY-MM-DD")
    ref = reference(invoice_number)
    if not ref:
        raise ValueError("the invoice has no number that can be a reference")
    record = {
        "pack": PACK, "pack_version": PACK_VERSION, "kind": "invoice.issued",
        "record_id": "odoo-move-%d" % int(move_id),
        "invoice_ref": ref, "issued_on": invoice_date,
        "invoice_digest": file_sha256, "invoice_format": invoice_format(mimetype, filename),
    }
    if partner_id:
        record["customer_ref"] = "odoo-partner-%d" % int(partner_id)
    supply = reference(origin)
    if supply:
        record["supply_ref"] = supply
    return record


def received_record(move_id, supplier_invoice_number, received_at, file_sha256, mimetype, filename="", partner_id=None):
    """An invoice.received record for a posted vendor bill or refund, sealed by the file received."""
    if not DIGEST.match(file_sha256 or ""):
        raise ValueError("the invoice file's SHA-256 is not a lowercase hex digest")
    if not TIMESTAMP.match(received_at or ""):
        raise ValueError("the reception time is not YYYY-MM-DDTHH:MM:SSZ")
    if not partner_id:
        raise ValueError("the bill has no supplier")
    ref = reference(supplier_invoice_number)
    if not ref:
        raise ValueError("the bill has no supplier invoice number (Bill Reference) that can be a reference")
    return {
        "pack": PACK, "pack_version": PACK_VERSION, "kind": "invoice.received",
        "record_id": "odoo-move-%d" % int(move_id),
        "invoice_ref": ref, "supplier_ref": "odoo-partner-%d" % int(partner_id),
        "received_at": received_at, "invoice_digest": file_sha256,
        "invoice_format": invoice_format(mimetype, filename),
    }
