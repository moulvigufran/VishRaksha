"""Run the VishRaksha agent from the command line.

  python run_demo.py                 # all five scenarios
  python run_demo.py first_fails     # one scenario
  python run_demo.py normal --llm    # read the call note with Claude (needs ANTHROPIC_API_KEY)
  python run_demo.py stock           # the 8 AM stock check-in agent
  python run_demo.py rescue          # doctor refers a patient: find a ventilator bed
"""
import sys

from vishraksha.agent import ReachAgent, print_trace
from vishraksha.scenarios import SCENARIOS
from vishraksha.stock_agent import run_checkin
from vishraksha.tools import SimulatedWorld


def main(args):
    use_llm = "--llm" in args
    args = [a for a in args if not a.startswith("--")]
    if args and args[0] == "stock":
        log, table, proposals = run_checkin(
            replies={"chc_tilda": "18", "chc_amlidih": "12 vial", "phc_khedi": "sirf 4 bache hain",
                     "dh": "40", "mc": "60 vials", "phc_sonpur": None, "phc_rampur": None},
            keypad={"phc_sonpur": "10", "phc_rampur": None})
        for kind, text in log:
            print(f"{kind:<10} {text}")
        print("\nStock table:", table)
        print("Proposals (need human approval):", proposals)
        return
    if args and args[0] == "rescue":
        world = SimulatedWorld({"dh": [("ready", 1.8)], "mc": [("ready", 2.5)]})
        res = ReachAgent(world, need="ventilator").run("VR-RESCUE-01", village="Tilda")
        print_trace(res)
        return
    parser = None
    if use_llm:
        from vishraksha.llm import parse_call_note_llm
        parser = parse_call_note_llm
    for key in (args or SCENARIOS):
        sc = SCENARIOS[key]
        print("=" * 100, f"\nSCENARIO: {sc['title']}\n" + "=" * 100)
        res = ReachAgent(sc["world"](), parser=parser).run(f"VR-{key.upper()}", sc["note"])
        print_trace(res)
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
