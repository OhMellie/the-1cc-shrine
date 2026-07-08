"""Static seed data: mainline games TH06-TH20 and their shot types.

Source: Touhou Wiki. Each shot type is (name, main_eligible, extra_eligible):
  main_eligible  - can play Easy/Normal/Hard/Lunatic
  extra_eligible - can play the Extra stage
Notes:
  - TH07 PCB Phantasm eligibility is not stored here; every PCB shot type
    can play Phantasm, handled in code (game number 7).
  - TH09 PoFV and TH19 UDoALG have no Extra stage: extra_eligible False.
  - TH16 HSiFS Extra locks the sub-season to Doyou, so Extra is tracked as
    four extra-only rows (main_eligible False) instead of per season combo.
"""

GAMES = [
    # (number, title, year)
    (6,  "Embodiment of Scarlet Devil", 2002),
    (7,  "Perfect Cherry Blossom", 2003),
    (8,  "Imperishable Night", 2004),
    (9,  "Phantasmagoria of Flower View", 2005),
    (10, "Mountain of Faith", 2007),
    (11, "Subterranean Animism", 2008),
    (12, "Undefined Fantastic Object", 2009),
    (13, "Ten Desires", 2011),
    (14, "Double Dealing Character", 2013),
    (15, "Legacy of Lunatic Kingdom", 2015),
    (16, "Hidden Star in Four Seasons", 2017),
    (17, "Wily Beast and Weakest Creature", 2019),
    (18, "Unconnected Marketeers", 2021),
    (19, "Unfinished Dream of All Living Ghost", 2023),
    (20, "Fossilized Wonders", 2025),
]


def _standard(names):
    """Shot types playable on all main difficulties and Extra."""
    return [(n, True, True) for n in names]


def _no_extra(names):
    """Games without an Extra stage (PoFV, UDoALG)."""
    return [(n, True, False) for n in names]


SHOT_TYPES = {
    6: _standard([
        "Reimu A (Homing Amulet)",
        "Reimu B (Persuasion Needle)",
        "Marisa A (Magic Missile)",
        "Marisa B (Illusion Laser)",
    ]),
    7: _standard([
        "Reimu A (Spirit Sign)",
        "Reimu B (Dream Sign)",
        "Marisa A (Magic Sign)",
        "Marisa B (Love Sign)",
        "Sakuya A (Illusion Sign)",
        "Sakuya B (Time Sign)",
    ]),
    8: _standard([
        "Border Team (Reimu & Yukari)",
        "Magic Team (Marisa & Alice)",
        "Scarlet Devil Team (Sakuya & Remilia)",
        "Netherworld Team (Youmu & Yuyuko)",
        "Reimu (solo)",
        "Yukari (solo)",
        "Marisa (solo)",
        "Alice (solo)",
        "Sakuya (solo)",
        "Remilia (solo)",
        "Youmu (solo)",
        "Yuyuko (solo)",
    ]),
    9: _no_extra([
        "Reimu", "Marisa", "Sakuya", "Youmu", "Reisen", "Cirno",
        "Lyrica", "Mystia", "Tewi", "Aya", "Medicine", "Yuuka",
        "Komachi", "Eiki",
    ]),
    10: _standard([
        "Reimu A (Homing)",
        "Reimu B (Forward Focus)",
        "Reimu C (Sealing)",
        "Marisa A (Magic Missile)",
        "Marisa B (Piercing Laser)",
        "Marisa C (Magic Options)",
    ]),
    11: _standard([
        "Reimu A (Yukari)",
        "Reimu B (Suika)",
        "Reimu C (Aya)",
        "Marisa A (Alice)",
        "Marisa B (Patchouli)",
        "Marisa C (Nitori)",
    ]),
    12: _standard([
        "Reimu A (Homing Amulet)",
        "Reimu B (Persuasion Needle)",
        "Marisa A (Illusion Laser)",
        "Marisa B (Magic Missile)",
        "Sanae A (Cobalt Spread)",
        "Sanae B (Snake & Frog)",
    ]),
    13: _standard(["Reimu", "Marisa", "Sanae", "Youmu"]),
    14: _standard([
        "Reimu A (Homing)",
        "Reimu B (Gap)",
        "Marisa A (Laser)",
        "Marisa B (Missile)",
        "Sakuya A (Knives)",
        "Sakuya B (Time)",
    ]),
    15: _standard(["Reimu", "Marisa", "Sanae", "Reisen"]),
    16: (
        # 16 season combos: main game only (Extra forces the Doyou sub-season)
        [(f"{char} ({season})", True, False)
         for char in ("Reimu", "Cirno", "Aya", "Marisa")
         for season in ("Spring", "Summer", "Autumn", "Winter")]
        # 4 extra-only rows
        + [(f"{char} (Doyou / Extra)", False, True)
           for char in ("Reimu", "Cirno", "Aya", "Marisa")]
    ),
    17: _standard([
        f"{char} ({beast})"
        for char in ("Reimu", "Marisa", "Youmu")
        for beast in ("Wolf", "Otter", "Eagle")
    ]),
    18: _standard(["Reimu", "Marisa", "Sakuya", "Sanae"]),
    19: _no_extra([
        "Reimu", "Marisa", "Sanae", "Ran", "Aunn", "Nazrin", "Seiran",
        "Rin", "Tsukasa", "Mamizou", "Yachie", "Saki", "Yuuma", "Suika",
        "Biten", "Enoko", "Chiyari", "Hisami", "Zanmu",
    ]),
    20: _standard(["Reimu", "Marisa"]),
}
