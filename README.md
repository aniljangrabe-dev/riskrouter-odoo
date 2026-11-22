# RiskRouter for Odoo

`riskrouter_seal` (Odoo 18): seal each posted invoice and bill in RiskRouter's append-only evidence log, and attach a
receipt anyone can check offline with the published verifiers (https://riskrouter.eu/verify). Only the salted SHA-256
of a small record leaves Odoo; no amount, name, email or file. See `riskrouter_seal/README.md`.

Apache-2.0. Copied from the RiskRouter repository; changes are made there.
