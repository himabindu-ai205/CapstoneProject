import os

from desk.approval import decide, execute, propose
from desk.pulse_view import pulse_text

DRAFT_TO = "product@groww"


def release(conn, sink: dict, pulse: dict, kind: str, call) -> str:
    """Approve one pulse write and hand that payload to Google. Returns a notice code."""
    if not pulse.get("ready"):
        return "empty"
    body = pulse_text(pulse)
    if kind == "append_doc":
        document_id = os.environ.get("GOOGLE_DOC_ID", "").strip()
        if not document_id:
            return "need-doc"
        spaced = f"\n\n{body.strip()}\n"
        action_id = propose(conn, "append_doc", document_id, spaced)
        decide(conn, action_id, "approved")
        try:
            call("append_to_google_doc", {"documentId": document_id, "content": spaced})
        except Exception:
            return "failed"
        execute(conn, action_id, sink)
        return "appended"
    if kind == "email_draft":
        recipient = os.environ.get("PULSE_DRAFT_TO", "").strip() or DRAFT_TO
        subject = f"Weekly product pulse {pulse.get('subtitle') or ''}".strip()
        action_id = propose(conn, "email_draft", recipient, body)
        decide(conn, action_id, "approved")
        try:
            call(
                "create_email_draft",
                {"to": [recipient], "subject": subject, "body": body},
            )
        except Exception:
            return "failed"
        execute(conn, action_id, sink)
        return "drafted"
    raise ValueError(kind)
