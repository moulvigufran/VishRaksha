# VishRaksha Agent

**Snakebite to antivenom in 60 minutes.**
An AI agent that reads a 108 emergency call note, finds health centres that have antivenom and a doctor tonight, calls them by itself, locks the first one that says YES, sends the ambulance there and checks that the patient arrived. When something fails, it re-plans or hands over to a human.

Project Eclipse 2026 · OPEN-X track · Team InnoVerse

- **Live demo:** open `index.html` (GitHub Pages link in the repo description) — no install needed
- **Final deck:** `docs/VishRaksha_Eclipse_Round2.pdf`

## The problem

India has about 58,000 snakebite deaths a year (Million Death Study). The ambulance usually reaches *a* centre quickly, but the nearest centre often has no antivenom or no doctor at night, and the patient loses an hour or more in referrals. Nobody checks, before the patient leaves, which centre is ready right now.

## What the agent does

| Job | Trigger | What happens |
|---|---|---|
| **Reach** | Snakebite 108 call | Read the note (Hinglish) → find centres within 60 min with 10+ vials and a doctor → call the best 2 in parallel (press 1 / 2) → lock the first YES → send the ambulance → brief the centre → verify arrival |
| **Rescue** | Doctor presses Refer | Bedside timer for the national protocol checks (doctor enters what they see) → find and confirm a ventilator bed → send a handover note |
| **Restock** | Every day at 8 AM | Ask every centre for its vial count → chase non-replies by voice call → mark unknown and alert the Block officer → propose stock transfers, which a human approves |

The agent follows the loop **INPUT → UNDERSTAND → PLAN → TOOL USE → DECISION → ACTION → VERIFY → ESCALATE** and writes every step to a time-stamped trace.

## Failure handling (all covered by tests or demo scenarios)

| What goes wrong | What the agent does |
|---|---|
| Centre does not answer in 2 min | Moves on (the best 2 are always called together) |
| Centre presses 2 | Re-plans with the next centres |
| No ready centre within 60 min | Alerts the control room and widens to 90 min |
| Every centre declines | Pre-agreed fallback (Medical College) + District officer alert |
| Voice API error | Retries once, then WhatsApp buttons |
| Village name unclear | Asks the caller to confirm; if not confirmed, a human takes over |
| Stock data older than 24 h | Keeps the centre, but the call must confirm stock |
| Not a snakebite | Leaves the case to the normal 108 flow |

## Safety

- The agent never diagnoses and never suggests treatment. It only routes, reminds and records. Doctors decide.
- The ambulance never waits for the agent: it leaves at once and the destination reaches it on the way.
- Humans approve high-impact steps (unclear location, stock transfers, all centres declining).
- Minimal data: no ID numbers, masked phone numbers.

## Run it

```bash
# Python 3.10+
python run_demo.py                 # all 5 Reach scenarios with full trace
python run_demo.py first_fails     # one scenario
python run_demo.py rescue          # ventilator referral
python run_demo.py stock           # 8 AM stock check-in agent

pip install pytest
python -m pytest -q                # 10 tests

python simulation/simulate.py      # 10,000-bite monsoon simulation

# Optional: read call notes with Claude instead of rules
pip install anthropic
export ANTHROPIC_API_KEY=...
python run_demo.py normal --llm
```

Web demo: open `index.html` in any browser. It runs the same agent logic in JavaScript, fully offline.

## Simulation result (planning model, not field data)

| Metric | Today | With VishRaksha |
|---|---|---|
| Reached a ready centre within 60 min | 64% | 92% |
| Ready centre at the first stop | 49% | 95% |
| Median minutes to a ready centre | 38 | 26 |
| Slowest 10% (90th percentile), minutes | 159 | 57 |

Assumptions are at the top of `simulation/simulate.py`.

## Project layout

```
index.html               web demo (GitHub Pages)
run_demo.py              command-line demo
vishraksha/
  data.py                demo district: villages, centres, stock (simulated)
  tools.py               tools: parse_call_note, find_facilities, ivr_call, send_whatsapp, notify_ambulance, ...
  agent.py               Reach / Rescue agent loop with re-planning and escalation
  stock_agent.py         8 AM stock check-in agent
  llm.py                 optional Claude call-note reader (structured JSON output)
  scenarios.py           the 5 demo scenarios
simulation/simulate.py   10,000-case monsoon simulation
tests/test_agent.py      10 tests
docs/                    final deck (PDF)
```

## Real services in a pilot

| Tool in code | Real service |
|---|---|
| `ivr_call` | Exotel / Twilio voice with keypad input |
| `send_whatsapp` | WhatsApp Cloud API |
| `find_facilities` | ABDM Health Facility Registry + stock table |
| stock table | DVDMS / e-Aushadhi + the 8 AM check-in |
| `notify_ambulance` | State 108 dispatch (needs a state tie-up) |
| `get_eta` | OSRM / maps API |

## Known limitations

- Hospitals, phone numbers, stock and the ambulance are simulated in this repo.
- Real duty numbers and a 108 link need permission from the state health department.
- Stock is only as fresh as the morning check-in, so every call re-confirms it.

## Team

- Manas Girdhar — Team Leader & Technical Lead
- Moulvi Gufran — Clinical partner (final-year MBBS)

MIT License.
