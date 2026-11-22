# RiskRouter: seal invoices in a public evidence log (Odoo 18)

Each posted customer invoice or credit note, and if you choose each vendor bill, is sealed in RiskRouter's
append-only evidence log, and a receipt is attached to the invoice. Anyone can check that receipt offline with the
published verifiers, without Odoo and without RiskRouter: <https://riskrouter.eu/verify>.

**What leaves Odoo.** The SHA-256 of a small salted record and its kind, nothing else. The record is a
`vat-invoice` record (<https://riskrouter.eu/packs/vat-invoice.json>): the invoice number, its date, the SHA-256 of
the invoice PDF (or of the bill's attached file), the file's format, and ids such as `odoo-partner-42`. No amount,
no name, no email, no file. The record and its salt are kept on the invoice, and in the receipt.

**What a receipt shows.** That this record, naming this exact file, existed unchanged by the time the log sealed it.
It does not show that the invoice is correct, that it was delivered, or that it meets any rule.

## Install and set up

1. Put `riskrouter_seal` in your addons path and install *RiskRouter: seal invoices* (it depends on Accounting).
2. Accounting, Settings, *Evidence seal (RiskRouter)*: paste an API key. A sandbox key needs no account
   (<https://riskrouter.eu/integrate>); entries in the log are permanent and cannot be deleted.
3. Choose what to seal. Invoices dated before the first run are left alone, unless you set an earlier date.

A scheduled job runs every five minutes. An invoice is sealed once it is posted and its PDF exists (after *Send* or
*Print*); a bill once a file is attached. *Seal now*, on the invoice's *Evidence seal* tab, runs it at once.

If the log cannot be reached, or the key is wrong, the record stays saved and *Waiting for the log*, and the same
record is sent on the next run. Posting an invoice never waits for the log and never fails because of it.

## Licence

Apache-2.0 (`LICENSE`). `lib/riskrouter_recorder.py` is the RiskRouter Python recorder, unchanged.
