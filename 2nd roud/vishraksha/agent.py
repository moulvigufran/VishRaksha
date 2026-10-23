"""VishRaksha Reach / Rescue agent.

Goal: get a snakebite patient to a centre that has a doctor AND antivenom
(or a ventilator bed, for the Rescue job) within 60 minutes, and prove it.

The loop follows the trace Project Eclipse asks for:
INPUT -> UNDERSTAND -> PLAN -> TOOL USE -> DECISION -> ACTION -> VERIFY -> ESCALATE.
The agent never diagnoses and never advises treatment. It only finds,
confirms and readies a centre; every clinical decision stays with the doctor.
"""
from dataclasses import dataclass, field

from . import tools
from .data import TARGET_MIN, facility

SEARCH_TIERS = [TARGET_MIN, 90]   # widen once before the always-accept fallback
CONFIDENCE_OK = 0.9


@dataclass
class Step:
    t: float
    kind: str
    text: str


@dataclass
class CaseResult:
    case_id: str
    status: str = "open"
    destination: str | None = None
    eta: int | None = None
    minutes_to_lock: float = 0.0
    hospitals_contacted: int = 0
    failures_handled: list = field(default_factory=list)
    trace: list = field(default_factory=list)


class ReachAgent:
    def __init__(self, world: tools.SimulatedWorld, parser=None, need="antivenom"):
        self.world = world
        self.parser = parser or tools.parse_call_note
        self.need = need
        self.clock = 0.0

    def log(self, res: CaseResult, kind: str, text: str):
        res.trace.append(Step(round(self.clock, 1), kind, text))

    def run(self, case_id: str, note: str = "", village: str | None = None) -> CaseResult:
        res = CaseResult(case_id)
        self.log(res, "INPUT", note or f"Doctor referral from {village}: needs {self.need}")

        # 1. UNDERSTAND
        if village is None:
            info = self.parser(note)
            self.log(res, "UNDERSTAND", f"snakebite={info['is_snakebite']}, village={info['village_text']} "
                                        f"(confidence {info['village_confidence']}), bite {info['minutes_since_bite']} min ago")
            if not info["is_snakebite"]:
                self.log(res, "DECISION", "Not a snakebite. Leave the case to the normal 108 flow.")
                res.status = "not_snakebite"
                return res
            village = info["village_text"]
            if info["village_confidence"] < CONFIDENCE_OK:
                self.log(res, "TOOL", f"confirm_village_with_caller('{village}')")
                self.clock += 1
                if not tools.confirm_village_with_caller(self.world, village):
                    tools.alert_human(self.world, "108 control room", f"Case {case_id}: location unclear, please talk to caller")
                    self.log(res, "ESCALATE", "Caller did not confirm the village. Human control-room operator takes over.")
                    res.status = "handed_to_human"
                    res.failures_handled.append("unclear location")
                    return res
                res.failures_handled.append("unclear location (confirmed by caller)")
                self.log(res, "VERIFY", f"Caller pressed 1: location is {village}.")

        # 2. PLAN
        self.log(res, "PLAN", f"Find centres with a doctor and {self.need} within {TARGET_MIN} min of {village}; "
                              "call the best 2 in parallel; lock the first YES; send the ambulance; "
                              "brief the centre; verify arrival. Widen the search or escalate if all say no.")

        if note:
            self.log(res, "ACTION", "108 ambulance leaves at once towards the main road. The confirmed destination reaches the driver on the way.")

        tried, skipped = set(), set()
        locked = None
        for tier_i, max_eta in enumerate(SEARCH_TIERS):
            while locked is None:
                cands, rejected = tools.find_facilities(village, self.need, max_eta, exclude=tried)
                self.log(res, "TOOL", f"find_facilities(village={village}, need={self.need}, max_eta={max_eta}) -> "
                                      f"{[c['name'] + ' ' + str(c['eta']) + 'm' for c in cands]}")
                for r in rejected:
                    if r["id"] not in skipped and "min away" not in r["why_not"]:
                        skipped.add(r["id"])
                        self.log(res, "DECISION", f"Skip {r['name']}: {r['why_not']}.")
                if not cands:
                    break
                batch = cands[:2]
                for c in batch:
                    if c["stale"]:
                        self.log(res, "DECISION", f"{c['name']} stock data is over 24 h old. Keep it, but the call must confirm stock.")
                answers = [self._contact(res, c) for c in batch]
                res.hospitals_contacted += len(batch)
                yes = sorted([a for a in answers if a["answer"] == "ready"], key=lambda a: a["after"])
                if yes:
                    win = yes[0]
                    self.clock += win["after"]
                    locked = next(c for c in batch if c["id"] == win["id"])
                    self.log(res, "DECISION", f"{locked['name']} said READY first. Lock it.")
                    for c in batch:
                        if c["id"] != locked["id"] and any(a["id"] == c["id"] and a["answer"] == "ready" for a in answers):
                            tools.send_whatsapp(self.world, c["id"], "Stand down, thank you. Patient is going elsewhere.", ())
                            self.log(res, "ACTION", f"Stand-down message to {c['name']}.")
                else:
                    self.clock += max(a["after"] for a in answers)
                    for a in answers:
                        tried.add(a["id"])
                        res.failures_handled.append(f"{facility(a['id']).name}: {a['answer']}")
                    self.log(res, "DECISION", "No centre in this batch is ready. Re-plan with the next centres.")
            if locked:
                break
            if tier_i + 1 < len(SEARCH_TIERS):
                tools.alert_human(self.world, "108 control room", f"Case {case_id}: no ready centre within {max_eta} min")
                self.log(res, "ESCALATE", f"No ready centre within {max_eta} min. Control room told; widening the search to {SEARCH_TIERS[tier_i + 1]} min.")

        if locked is None:
            mc = next(f for f in tools.FACILITIES if f.always_accept)
            cands, _ = tools.find_facilities(village, self.need, 999)
            eta = next(c["eta"] for c in cands if c["id"] == mc.id)
            locked = {"id": mc.id, "name": mc.name, "eta": eta}
            tools.alert_human(self.world, "District officer", f"Case {case_id}: all centres declined; sent to {mc.name}")
            self.log(res, "ESCALATE", f"All centres declined. Use the pre-agreed fallback {mc.name} and alert the District officer.")
            res.failures_handled.append("all centres declined")

        # 3. ACTION
        msg = tools.notify_ambulance(self.world, case_id, locked["id"], locked["eta"])
        self.log(res, "ACTION", f"notify_ambulance -> '{msg['message']}'")
        tools.send_prearrival_note(self.world, locked["id"], {"case": case_id, "village": village, "eta": locked["eta"]})
        self.log(res, "ACTION", f"Pre-arrival note sent to {locked['name']}: village, bite time, ETA {locked['eta']} min.")
        res.minutes_to_lock = round(self.clock, 1)

        # 4. VERIFY
        self.clock += locked["eta"]
        ok = tools.verify_arrival(self.world, locked["id"])
        self.log(res, "VERIFY", f"At ETA, {locked['name']} pressed 1: patient received. Case closed." if ok
                 else f"Arrival not confirmed. Calling ambulance and control room.")
        res.status = "closed" if ok else "check_arrival"
        res.destination, res.eta = locked["name"], locked["eta"]
        return res

    def _contact(self, res, c):
        """Call one centre. Retry once on API error, then fall back to WhatsApp."""
        for attempt in (1, 2):
            try:
                self.log(res, "TOOL", f"ivr_call({c['name']}, eta={c['eta']}) attempt {attempt}")
                a = tools.ivr_call(self.world, c["id"], c["eta"], self.need)
                self.log(res, "TOOL", f"  -> {c['name']}: {a['answer']} after {a['after']} min")
                return a
            except tools.ToolError as e:
                self.log(res, "DECISION", f"Voice call failed ({e}).")
                res.failures_handled.append(f"{c['name']}: voice API error")
        self.log(res, "TOOL", f"send_whatsapp({c['name']}) with buttons Ready / Not ready")
        a = tools.send_whatsapp(self.world, c["id"], f"Snakebite patient, ETA {c['eta']} min. Doctor and {self.need} ready?")
        self.log(res, "TOOL", f"  -> {c['name']} (WhatsApp): {a['answer']} after {a['after']} min")
        return a


def print_trace(res: CaseResult):
    for s in res.trace:
        print(f"[{s.t:6.1f} min] {s.kind:<10} {s.text}")
    print(f"\nRESULT: {res.status} | destination={res.destination} | ETA={res.eta} min | "
          f"locked after {res.minutes_to_lock} min | hospitals contacted={res.hospitals_contacted} | "
          f"failures handled={res.failures_handled}")
