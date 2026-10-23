"""Demo district: villages, facilities and road travel times.

All names, phone numbers and stock figures are SIMULATED for the demo.
In a pilot, facilities come from the ABDM Health Facility Registry and
stock from the state drug system (DVDMS / e-Aushadhi) plus the daily
check-in run by the Stock agent.
"""
from dataclasses import dataclass, field
from math import hypot

# Starting dose of antivenom in the national snakebite protocol is 8-10 vials,
# so a centre needs at least this many vials to be "antivenom-ready".
MIN_VIALS = 10
TARGET_MIN = 60          # the 60-minute promise: bite call -> antivenom-ready centre
STOCK_FRESH_HOURS = 24   # older stock data is treated as "confirm on the call"
ROAD_FACTOR = 1.35       # straight line km -> road km
NIGHT_SPEED_KMPH = 35    # rural ambulance speed at night


@dataclass
class Village:
    name: str
    x: float
    y: float
    aliases: tuple = ()


@dataclass
class Facility:
    id: str
    name: str
    kind: str            # PHC / CHC / DH / MC
    x: float
    y: float
    vials: int
    doctor_on_duty: bool
    ventilator: bool
    stock_age_h: float   # hours since the last stock update
    phone: str           # masked duty number
    always_accept: bool = False   # medical college: pre-agreed fallback
    notes: dict = field(default_factory=dict)


VILLAGES = [
    Village("Rampur", 8, 30, ("rampr", "raampur", "rampur nala")),
    Village("Khedi", 14, 8, ("kheri", "khedi tola")),
    Village("Tilda", 22, 22, ("tilla",)),
    Village("Sonpur", 30, 38, ("sonepur", "sonpura")),
    Village("Amlidih", 38, 24, ("amlidi", "amli")),
    Village("Bhatgaon", 44, 10, ("bhatgao", "bhatgav")),
    Village("Kusumi", 52, 34, ("kusmi",)),
]

FACILITIES = [
    Facility("phc_rampur", "PHC Rampur", "PHC", 9, 27, 0, True, False, 6, "+91-98xxxx1101"),
    Facility("phc_khedi", "PHC Khedi", "PHC", 13, 10, 4, True, False, 5, "+91-98xxxx1102"),
    Facility("chc_tilda", "CHC Tilda", "CHC", 22, 20, 18, True, False, 3, "+91-98xxxx1103"),
    Facility("phc_sonpur", "PHC Sonpur", "PHC", 31, 36, 10, True, False, 30, "+91-98xxxx1104"),
    Facility("chc_amlidih", "CHC Amlidih", "CHC", 37, 26, 12, True, False, 4, "+91-98xxxx1105"),
    Facility("dh", "District Hospital", "DH", 46, 18, 40, True, True, 2, "+91-98xxxx1106"),
    Facility("mc", "Govt Medical College", "MC", 55, 40, 60, True, True, 1, "+91-98xxxx1107", always_accept=True),
]


def eta_min(x1, y1, x2, y2) -> int:
    km = hypot(x2 - x1, y2 - y1) * ROAD_FACTOR
    return max(3, round(km / NIGHT_SPEED_KMPH * 60))


def facility(fid: str) -> Facility:
    return next(f for f in FACILITIES if f.id == fid)
