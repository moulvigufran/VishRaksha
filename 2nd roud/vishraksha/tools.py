"""Tools the agent can call.

Each tool is a plain function with a clear input and output so it can be
swapped for the real service in a pilot:

  ivr_call        -> Exotel / Twilio voice call with keypad input (press 1 / 2)
  send_whatsapp   -> WhatsApp Cloud API template message with buttons
  notify_ambulance-> 108 dispatch system (state tie-up), simulated here
  get_eta         -> OSRM / Google Distance Matrix, simulated with road factor
  query_stock     -> DVDMS / e-Aushadhi + daily check-in table

In this repo the outside world (hospitals, phones, ambulance) is a
SimulatedWorld, so the demo runs offline and every failure can be replayed.
"""
import re
from difflib import SequenceMatcher

from .data import FACILITIES, VILLAGES, MIN_VIALS, STOCK_FRESH_HOURS, eta_min, facility


class ToolError(Exception):
    """A tool failed (API down, timeout). The agent must handle it."""


class SimulatedWorld:
    """Scripted behaviour of the outside world for one scenario.

    hospital_script: {facility_id: [response, response, ...]} one entry per call.
      response = ("ready", minutes) | ("not_ready", minutes) | ("no_answer",) | ("error",)
    whatsapp_script: {facility_id: ("ready", minutes) | ("no_answer",)}
    caller_confirms: what the caller presses when asked to confirm the village.
    """

    def __init__(self, hospital_script=None, whatsapp_script=None, caller_confirms=True):
        self.hospital_script = {k: list(v) for k, v in (hospital_script or {}).items()}
        self.whatsapp_script = whatsapp_script or {}
        self.caller_confirms = caller_confirms
        self.outbox = []          # every message / call the agent made

    def next_call_result(self, fid):
        script = self.hospital_script.get(fid)
        if not script:
            return ("ready", 1.5)
        return script.pop(0) if len(script) > 1 else script[0]


# ---------- understanding the input ----------

SNAKE_WORDS = ("snake", "saanp", "sanp", "saap", "nag", "naag", "krait", "cobra", "viper", "sarp", "kaata", "kata", "dans")


def parse_call_note(text: str) -> dict:
    """Rule-based reader for the 108 call-taker's free-text note (Hinglish).

    Used when no LLM key is set. vishraksha.llm.parse_call_note_llm does the
    same job with Claude and returns the same fields.
    """
    t = text.lower()
    is_snakebite = any(w in t for w in SNAKE_WORDS)
    mins = None
    m = re.search(r"(\d+)\s*(min|minute|mins|minat)", t)
    if m:
        mins = int(m.group(1))
    h = re.search(r"(\d+)\s*(ghante|ghanta|hour|hr)", t)
    if h:
        mins = int(h.group(1)) * 60
    words = re.findall(r"[a-z]+", t)
    best, score = None, 0.0
    for v in VILLAGES:
        for i, name in enumerate((v.name.lower(),) + tuple(v.aliases)):
            for w in words:
                s = SequenceMatcher(None, w, name.split()[0]).ratio()
                if not (i == 0 and s == 1.0):
                    s *= 0.85   # not an exact match of the real name: the agent will ask the caller
                if s > score:
                    best, score = v.name, s
    phone = re.search(r"(\+?\d[\d\- ]{8,}\d)", text)
    return {
        "is_snakebite": is_snakebite,
        "village_text": best,
        "village_confidence": round(score, 2),
        "minutes_since_bite": mins,
        "caller_phone": phone.group(1) if phone else None,
    }


def confirm_village_with_caller(world: SimulatedWorld, village: str) -> bool:
    """IVR call-back: 'Are you near <village>? Press 1 for yes, 2 for no.'"""
    world.outbox.append(("ivr_confirm_village", village))
    return world.caller_confirms


# ---------- finding centres ----------

def find_facilities(village: str, need: str, max_eta: int, exclude=()):
    """Return (candidates, rejected) for a need: 'antivenom' or 'ventilator'."""
    v = next(x for x in VILLAGES if x.name == village)
    candidates, rejected = [], []
    for f in FACILITIES:
        if f.id in exclude:
            continue
        eta = eta_min(v.x, v.y, f.x, f.y)
        reasons = []
        if f.vials < MIN_VIALS:
            reasons.append(f"only {f.vials} vials")
        if not f.doctor_on_duty:
            reasons.append("no doctor on duty")
        if need == "ventilator" and not f.ventilator:
            reasons.append("no ventilator")
        if eta > max_eta:
            reasons.append(f"{eta} min away")
        row = {"id": f.id, "name": f.name, "eta": eta, "vials": f.vials,
               "stale": f.stock_age_h > STOCK_FRESH_HOURS}
        (rejected if reasons else candidates).append({**row, "why_not": ", ".join(reasons)})
    candidates.sort(key=lambda r: r["eta"])
    rejected.sort(key=lambda r: r["eta"])
    return candidates, rejected


# ---------- talking to hospitals ----------

CALL_TIMEOUT_MIN = 2.0


def ivr_call(world: SimulatedWorld, fid: str, eta: int, need: str) -> dict:
    """Automated voice call to the duty number. Raises ToolError if the line fails."""
    f = facility(fid)
    script = (f"VishRaksha emergency alert. A snakebite patient will reach {f.name} in about {eta} minutes. "
              f"Press 1 if a doctor and {'a ventilator bed' if need == 'ventilator' else 'antivenom'} are ready. Press 2 if not.")
    world.outbox.append(("ivr_call", fid, script))
    res = world.next_call_result(fid)
    if res[0] == "error":
        raise ToolError(f"voice API returned 503 for {f.phone}")
    if res[0] == "no_answer":
        return {"id": fid, "answer": "no_answer", "after": CALL_TIMEOUT_MIN}
    return {"id": fid, "answer": res[0], "after": res[1]}


def send_whatsapp(world: SimulatedWorld, fid: str, text: str, buttons=("Ready", "Not ready")) -> dict:
    world.outbox.append(("whatsapp", fid, text, buttons))
    res = world.whatsapp_script.get(fid, ("no_answer",))
    if res[0] == "no_answer":
        return {"id": fid, "answer": "no_answer", "after": 5.0}
    return {"id": fid, "answer": res[0], "after": res[1]}


def notify_ambulance(world: SimulatedWorld, case_id: str, fid: str, eta: int) -> dict:
    f = facility(fid)
    world.outbox.append(("ambulance", case_id, fid))
    return {"ok": True, "message": f"Go to {f.name}. ETA {eta} min. Hospital confirmed ready."}


def send_prearrival_note(world: SimulatedWorld, fid: str, note: dict) -> dict:
    world.outbox.append(("prearrival", fid, note))
    return {"ok": True}


def verify_arrival(world: SimulatedWorld, fid: str) -> bool:
    """Calls the receiving centre at ETA: 'Patient received? Press 1'."""
    world.outbox.append(("verify", fid))
    return True


def alert_human(world: SimulatedWorld, role: str, text: str) -> dict:
    world.outbox.append(("alert", role, text))
    return {"ok": True, "to": role}
