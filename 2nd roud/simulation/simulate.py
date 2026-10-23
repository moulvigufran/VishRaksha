"""Monsoon simulation: 10,000 snakebite emergencies in one synthetic district.

TODAY: the patient is taken to the nearest government facility. If it has no
antivenom (fewer than 10 vials) or no doctor on duty at that hour, the patient
is referred on (20 min paperwork + arranging transport) to the next nearest
facility, up to the District Hospital.

WITH VISHRAKSHA: the ambulance leaves at once; the agent calls the best 2
centres in parallel and sends the ambulance straight to the nearest centre
that confirms READY (2 min for the calls, a few min lost if the ambulance must
turn). Stock data that is wrong or old is caught by the call.

All numbers are assumptions for a planning model, not field data. They are
listed at the top so judges and mentors can change them.
"""
import random
import statistics
from math import hypot

SEED = 7
N_BITES = 10_000
AREA_KM = 70
ROAD_FACTOR, SPEED = 1.35, 35
P_READY = {"PHC": 0.40, "CHC": 0.80, "DH": 0.97}   # has >=10 vials AND a doctor, at a random night hour
N_FAC = {"PHC": 22, "CHC": 6, "DH": 1}
REFERRAL_DELAY = 20
CALL_OVERHEAD = 2
TURN_PENALTY = 4   # minutes lost when the first heading was wrong
P_WRONG_YES = 0.05 # centre pressed 1 but could not treat on arrival (human error)


def eta(a, b):
    return hypot(a[0] - b[0], a[1] - b[1]) * ROAD_FACTOR / SPEED * 60


def run(seed=SEED):
    rnd = random.Random(seed)
    facs = []
    for kind, n in N_FAC.items():
        for _ in range(n):
            pos = (AREA_KM / 2, AREA_KM / 2) if kind == "DH" else (rnd.uniform(0, AREA_KM), rnd.uniform(0, AREA_KM))
            facs.append({"kind": kind, "pos": pos})
    base, agent, base_first, agent_first = [], [], 0, 0
    for _ in range(N_BITES):
        home = (rnd.uniform(0, AREA_KM), rnd.uniform(0, AREA_KM))
        ready = {i: (f["kind"] == "DH" and rnd.random() < 0.995) or rnd.random() < P_READY[f["kind"]] for i, f in enumerate(facs)}
        dh = next(i for i, f in enumerate(facs) if f["kind"] == "DH")
        ready[dh] = True
        order = sorted(range(len(facs)), key=lambda i: eta(home, facs[i]["pos"]))
        # today
        t, pos, hops = 0.0, home, 0
        for i in order:
            t += eta(pos, facs[i]["pos"]) + (REFERRAL_DELAY if hops else 0)
            pos = facs[i]["pos"]
            if ready[i]:
                break
            hops += 1
            if hops == 3:   # after 3 failed stops, straight to the DH
                t += REFERRAL_DELAY + eta(pos, facs[dh]["pos"])
                break
        base.append(t)
        base_first += hops == 0
        # with VishRaksha
        best = next(i for i in order if ready[i])
        t2 = eta(home, facs[best]["pos"]) + CALL_OVERHEAD + (0 if best == order[0] else TURN_PENALTY)
        if rnd.random() < P_WRONG_YES:
            nxt = next(i for i in order if ready[i] and i != best)
            t2 += REFERRAL_DELAY + eta(facs[best]["pos"], facs[nxt]["pos"])
        else:
            agent_first += 1
        agent.append(t2)
    def summary(xs, first):
        xs = sorted(xs)
        return {"median_min": round(statistics.median(xs)), "p90_min": round(xs[int(0.9 * len(xs))]),
                "within_60_pct": round(100 * sum(x <= 60 for x in xs) / len(xs)),
                "ready_at_first_stop_pct": round(100 * first / len(xs))}
    return summary(base, base_first), summary(agent, agent_first)


if __name__ == "__main__":
    today, vr = run()
    print(f"{N_BITES} simulated monsoon snakebites, seed {SEED}")
    print(f"{'metric':<34}{'today':>8}{'VishRaksha':>12}")
    for k in today:
        print(f"{k:<34}{today[k]:>8}{vr[k]:>12}")
