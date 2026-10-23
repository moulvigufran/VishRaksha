"""Daily antivenom stock check-in agent (runs every morning at 8 AM).

1. WhatsApp each centre: "How many antivenom vials today?"
2. Read the reply (numbers or free text like "sirf 4 bache hain").
3. No reply in 30 min -> automated voice call, keypad entry.
4. Still nothing -> mark stock UNKNOWN and tell the Block officer.
5. Low stock -> PROPOSE moving vials from a centre with surplus.
   Moving stock is a high-impact action, so a human must approve it.
"""
import re
from .data import FACILITIES, MIN_VIALS, eta_min

SURPLUS_KEEP = 20   # a donor keeps at least this many vials


def read_vials(reply: str):
    m = re.search(r"\d+", reply or "")
    return int(m.group()) if m else None


def run_checkin(replies: dict, keypad: dict):
    """replies: {facility_id: whatsapp text or None}; keypad: {facility_id: digits or None}"""
    log, table, proposals = [], {}, []
    for f in FACILITIES:
        log.append(("TOOL", f"send_whatsapp({f.name}, 'How many antivenom vials today?')"))
        n = read_vials(replies.get(f.id))
        if n is None:
            log.append(("DECISION", f"{f.name}: no usable reply in 30 min. Calling."))
            log.append(("TOOL", f"ivr_call({f.name}, 'Enter vial count on keypad')"))
            n = read_vials(keypad.get(f.id))
        if n is None:
            table[f.id] = None
            log.append(("ESCALATE", f"{f.name}: stock UNKNOWN. Block officer alerted. Reach agent will confirm stock on every call."))
            continue
        table[f.id] = n
        log.append(("UNDERSTAND", f"{f.name}: {n} vials"))
    for f in FACILITIES:
        n = table.get(f.id)
        if n is not None and n < MIN_VIALS:
            donors = [d for d in FACILITIES if (table.get(d.id) or 0) - SURPLUS_KEEP >= MIN_VIALS - n]
            if donors:
                d = min(donors, key=lambda d: eta_min(d.x, d.y, f.x, f.y))
                qty = MIN_VIALS - n + 5
                proposals.append({"from": d.name, "to": f.name, "vials": qty, "status": "waiting for approval"})
                log.append(("PLAN", f"{f.name} has {n} vials (< {MIN_VIALS}). Propose moving {qty} vials from {d.name}. Needs District store officer approval."))
    return log, table, proposals
