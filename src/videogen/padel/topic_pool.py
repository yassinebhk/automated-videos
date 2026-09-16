"""Padel Pro (EN) tips pool — curated scripts (0 LLM cost) + animated play.
Court coords: x in [0,10], y in [0,20] (net at y=10). Every play has 4 players
(2 near, y<10; 2 far, y>=10) — padel is always 2v2."""
from __future__ import annotations


TOPICS = [
    {"key": "lob", "titulo": "The lob",
     "hook": "Getting passed at the net?",
     "narracion": "The lob is your reset button. When they crowd the net, don't panic. "
                  "Lift the ball high and deep so it dies near the back glass. "
                  "You buy time, push them back, and take the net yourself. Follow for more padel.",
     "play": {"ball": [(3, 4), (5, 13), (5, 18.5)],
              "players": [(3, 4), (6, 5), (3.6, 15.5), (6.4, 16.2)]}},
    {"key": "back_wall", "titulo": "The back wall",
     "hook": "Scared of the back wall?",
     "narracion": "The glass is your friend, not your enemy. Let the ball pass you, bounce, "
                  "hit the wall and drop. Wait with patience, turn side-on, and guide it deep. "
                  "No rush, no power. Just control. Follow for more padel.",
     "play": {"ball": [(5, 17), (5, 19.3), (5, 15)],
              "players": [(4, 3), (6.5, 3.5), (3.6, 15.5), (6.4, 16.2)]}},
    {"key": "bandeja", "titulo": "The bandeja",
     "hook": "Stop smashing everything.",
     "narracion": "The bandeja is the smartest shot in padel. Instead of a risky smash, "
                  "slice the ball with control, keep it low and deep, and stay at the net. "
                  "You keep the pressure without giving up your position. Follow for more.",
     "play": {"ball": [(5, 7), (5, 3), (8, 16)],
              "players": [(4.5, 7), (6, 7.5), (3.5, 15), (6.5, 15.5)]}},
    {"key": "positioning", "titulo": "Move as one",
     "hook": "You and your partner drift apart?",
     "narracion": "Play as one. Imagine a five meter rope tying you to your partner: "
                  "when one moves, the other follows. Cover the middle together, close the gaps, "
                  "and most points are already yours. Follow for more padel.",
     "play": {"ball": [(2, 10), (8, 10)],
              "players": [(3.5, 6), (6, 6.5), (4, 14), (7, 14.5)]}},
    {"key": "por_tres", "titulo": "The out-of-court smash",
     "hook": "Want the crowd-pleaser?",
     "narracion": "The por-tres is padel's signature smash. Bounce the ball so hard it flies "
                  "out over the back fence. Hit up and through with a fast wrist. "
                  "If it leaves the court, the point is yours. Follow for more padel.",
     "play": {"ball": [(5, 12), (5, 4), (5, 21)],
              "players": [(4.5, 7), (6, 7.5), (3, 15), (7, 15)]}},
    {"key": "drop_shot", "titulo": "The drop shot",
     "hook": "Rival stuck at the back?",
     "narracion": "The drop shot breaks their rhythm. With soft hands, cushion the ball "
                  "so it barely clears the net and dies short. Use it when they're deep near the glass. "
                  "Total surprise, easy point. Follow for more padel.",
     "play": {"ball": [(5, 15), (5, 11), (4.5, 9)],
              "players": [(4, 4), (6.5, 4.5), (3.5, 15.5), (6.5, 16)]}},
    {"key": "serve", "titulo": "The smart serve",
     "hook": "Serving to win the point? Wrong.",
     "narracion": "The serve isn't to win the point, it's to win the net. "
                  "Serve cross-court into the side wall to make the return awkward, "
                  "then move up with your partner immediately. Control the net, control the game.",
     "play": {"ball": [(3, 8), (7, 12), (8.5, 14)],
              "players": [(3, 7), (6, 7.5), (4, 13), (7, 13.5)]}},
    {"key": "double_wall", "titulo": "The double wall",
     "hook": "The double wall scares you?",
     "narracion": "The double wall looks impossible, but there's a trick. Open up, give yourself space, "
                  "and track the ball: back glass first, then side wall. Wait for it to come out, "
                  "then push it calmly to the middle. Follow for more padel.",
     "play": {"ball": [(5, 18), (2, 19.3), (5, 16)],
              "players": [(4, 5), (6, 5), (3.6, 15.5), (6.4, 16.2)]}},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str):
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
