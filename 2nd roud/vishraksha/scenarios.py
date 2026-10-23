"""The five demo scenarios (same as the web demo)."""
from .tools import SimulatedWorld

SCENARIOS = {
    "normal": dict(
        title="Normal night: nearest PHC has no antivenom",
        note="Raat 11:40. Ramu, 34, saanp ne kaata, Rampur gaon, 20 min pehle. Caller 98xxxx4521",
        world=lambda: SimulatedWorld({"chc_tilda": [("ready", 1.5)], "phc_sonpur": [("ready", 2.0)]}),
    ),
    "first_fails": dict(
        title="First choices fail: one says no, one does not answer",
        note="Snake bite, Rampur, 30 min ago, leg swelling. Caller 98xxxx7710",
        world=lambda: SimulatedWorld({"chc_tilda": [("not_ready", 1.0)], "phc_sonpur": [("no_answer",)],
                                      "chc_amlidih": [("ready", 1.2)], "dh": [("no_answer",)]}),
    ),
    "all_decline": dict(
        title="Everyone declines: fallback + District officer",
        note="saanp kaata Rampur 15 min",
        world=lambda: SimulatedWorld({k: [("not_ready", 1.0)] for k in
                                      ["chc_tilda", "phc_sonpur", "chc_amlidih", "dh"]}),
    ),
    "messy_input": dict(
        title="Messy note: village unclear, caller confirms",
        note="sanp ne dans liya, rampr ke paas nala, 1 ghante pehle",
        world=lambda: SimulatedWorld({"chc_tilda": [("ready", 1.0)]}),
    ),
    "api_down": dict(
        title="Voice API down: retry, then WhatsApp",
        note="Krait bite suspected, Rampur, 45 min ago",
        world=lambda: SimulatedWorld({"chc_tilda": [("error",), ("error",)], "phc_sonpur": [("not_ready", 1.5)]},
                                     whatsapp_script={"chc_tilda": ("ready", 2.5)}),
    ),
}
