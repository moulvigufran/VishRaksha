import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vishraksha.agent import ReachAgent
from vishraksha.scenarios import SCENARIOS
from vishraksha.stock_agent import run_checkin
from vishraksha.tools import parse_call_note, SimulatedWorld


def run(key):
    sc = SCENARIOS[key]
    return ReachAgent(sc["world"]()).run(key, sc["note"])


def test_skips_nearest_phc_without_antivenom():
    res = run("normal")
    assert res.destination == "CHC Tilda" and res.status == "closed"
    assert any("Skip PHC Rampur" in s.text for s in res.trace)


def test_replans_when_first_centres_fail():
    res = run("first_fails")
    assert res.destination == "CHC Amlidih"
    assert any(s.kind == "ESCALATE" for s in res.trace)


def test_all_decline_goes_to_fallback_and_alerts_officer():
    sc = SCENARIOS["all_decline"]
    world = sc["world"]()
    res = ReachAgent(world).run("x", sc["note"])
    assert res.destination == "Govt Medical College"
    assert any(o[0] == "alert" and o[1] == "District officer" for o in world.outbox)


def test_unclear_village_is_confirmed_with_caller():
    res = run("messy_input")
    assert any("confirm_village_with_caller" in s.text for s in res.trace)


def test_caller_says_no_hands_over_to_human():
    world = SimulatedWorld(caller_confirms=False)
    res = ReachAgent(world).run("x", "sanp kaata rampr ke paas")
    assert res.status == "handed_to_human"


def test_voice_api_down_falls_back_to_whatsapp():
    res = run("api_down")
    assert res.destination == "CHC Tilda"
    assert any("send_whatsapp" in s.text for s in res.trace)


def test_not_snakebite_is_left_to_108():
    res = ReachAgent(SimulatedWorld()).run("x", "Pet dard, Rampur, 2 ghante se")
    assert res.status == "not_snakebite"


def test_parser_reads_hinglish():
    info = parse_call_note("Raat 11:40. saanp ne kaata, Rampur gaon, 20 min pehle. Caller 98xxxx4521")
    assert info["is_snakebite"] and info["village_text"] == "Rampur" and info["minutes_since_bite"] == 20


def test_stock_agent_unknown_and_low_stock_needs_approval():
    log, table, proposals = run_checkin({"phc_khedi": "sirf 4 bache", "dh": "40"}, {})
    assert table["phc_khedi"] == 4 and table["phc_rampur"] is None
    assert proposals and proposals[0]["status"] == "waiting for approval"


def test_rescue_finds_ventilator():
    world = SimulatedWorld({"dh": [("ready", 1.8)]})
    res = ReachAgent(world, need="ventilator").run("r", village="Tilda")
    assert res.destination == "District Hospital"
