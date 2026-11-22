# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Anil Jangra
{
    "name": "RiskRouter: seal invoices in a public evidence log",
    "summary": "Seal each posted invoice and bill in an append-only log, and keep a receipt anyone can check offline. The invoice never leaves Odoo.",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "Anil Jangra",
    "website": "https://riskrouter.eu/integrate",
    "license": "Other OSI approved licence",
    "depends": ["account"],
    "data": [
        "data/ir_cron.xml",
        "views/account_move_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
