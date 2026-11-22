# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Anil Jangra
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    riskrouter_api_key = fields.Char("RiskRouter API key", config_parameter="riskrouter_seal.api_key")
    riskrouter_api_base = fields.Char("Evidence log", config_parameter="riskrouter_seal.api_base",
                                      default="https://api.riskrouter.eu")
    riskrouter_seal_issued = fields.Boolean("Seal customer invoices and credit notes",
                                            config_parameter="riskrouter_seal.seal_issued", default=True)
    riskrouter_seal_received = fields.Boolean("Seal vendor bills and refunds",
                                              config_parameter="riskrouter_seal.seal_received")
    riskrouter_since = fields.Char("Seal invoices dated from", config_parameter="riskrouter_seal.since",
                                   help="YYYY-MM-DD. Left empty, the first run sets it to that day, so the invoices "
                                        "posted before are not all sent at once.")
