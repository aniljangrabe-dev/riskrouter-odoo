# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Anil Jangra
"""The two calls this module makes to the evidence log, standard library only, so they can be tested
without Odoo: record a digest (POST /api/v2/evidence) and fetch its proof (GET /api/v2/evidence/proof).

Only the salted digest and the kind are sent (CLAUDE.md rule 15). Each answer is classified so the
caller never shows a seal the log did not confirm (rule 5):

- sealed:  the log answered 201 for this exact digest;
- refused: the log refused this entry (400 or 422); retrying the same record would be refused again;
- retry:   no answer, a server error, a rate limit, or a key problem (401, 403), which the owner fixes
           in the settings and which must not mark invoices as refused.
"""
import json
import urllib.error
import urllib.request

TIMEOUT = 20


def _call(method, url, key, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Authorization": "Bearer %s" % key, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status, json.loads(res.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8") or "null")
        except ValueError:
            payload = None
        return e.code, payload


def record(api, key, digest, kind):
    """Send one digest. Returns (outcome, entry or None, message)."""
    try:
        status, body = _call("POST", "%s/api/v2/evidence" % api.rstrip("/"), key, {"record_digest": digest, "kind": kind})
    except (urllib.error.URLError, OSError, ValueError) as e:
        return "retry", None, "the log could not be reached (%s)" % e
    entry = (body or {}).get("entry") if isinstance(body, dict) else None
    if status == 201 and isinstance(entry, dict) and entry.get("record_digest") == digest:
        return "sealed", entry, ""
    message = ((body or {}).get("error") or {}).get("message") if isinstance(body, dict) else None
    message = message or "the log answered %s" % status
    if status in (400, 422):
        return "refused", None, message
    return "retry", None, message


def proof(api, key, leaf_index):
    """The entry's inclusion proof, or None when it cannot be had yet."""
    try:
        status, body = _call("GET", "%s/api/v2/evidence/proof?leaf_index=%d" % (api.rstrip("/"), int(leaf_index)), key)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return body if status == 200 and isinstance(body, dict) else None
