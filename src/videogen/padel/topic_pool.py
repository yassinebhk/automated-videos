"""Padel Pro (EN) — consejos de pádel narrados sobre METRAJE REAL (Pexels).
Sin diagramas: el pipeline narrado fetchea clips reales de pádel por visual_keywords.
Cada topic = 1 consejo (subject curado para exactitud). Cooldown 90d."""
from __future__ import annotations


TOPICS = [
    {"key": "lob", "titulo": "The lob that wins the net back",
     "hook": "Getting passed at the net? Do this.",
     "subject": "When opponents take the net, lift a high, deep lob toward the back glass. "
                "It pushes them back and lets you recover the net. Aim deep, not hard."},
    {"key": "bandeja", "titulo": "Stop smashing — hit the bandeja",
     "hook": "You smash everything and lose the point?",
     "subject": "The bandeja is a controlled slice overhead: keep it low and deep, "
                "stay at the net instead of a risky flat smash. Control beats power."},
    {"key": "back_wall", "titulo": "Play off the back glass like a pro",
     "hook": "Scared of the back wall?",
     "subject": "Let the ball pass you, bounce, come off the glass and drop. Wait, turn side-on, "
                "and guide it deep with control. Patience, not power."},
    {"key": "positioning", "titulo": "Move as a pair",
     "hook": "You and your partner out of sync?",
     "subject": "Move together as if tied by a short rope. When one goes, the other follows. "
                "Cover the middle and close the gaps between you."},
    {"key": "por_tres", "titulo": "The out-of-court smash",
     "hook": "The most spectacular shot in padel.",
     "subject": "The por-tres: smash the ball so it bounces hard and flies out over the back fence. "
                "Hit up and through with a fast wrist. If it leaves the court, point won."},
    {"key": "serve", "titulo": "The smart serve",
     "hook": "Serving to win the point? Wrong.",
     "subject": "The serve is to win the net, not the point. Serve into the side wall to make the "
                "return awkward, then move up to the net with your partner immediately."},
    {"key": "drop_shot", "titulo": "The drop shot",
     "hook": "Rivals glued to the back wall?",
     "subject": "With soft hands, drop the ball short just over the net when opponents are deep. "
                "It breaks their rhythm and forces a weak reply."},
    {"key": "defense", "titulo": "Defend the smash",
     "hook": "Getting smashed on every point?",
     "subject": "Split-step, stay low, and block deep rather than swinging big. Use the side and "
                "back walls to buy time, and wait for your chance to lob and reset."},
]


def all_topics() -> list[dict]:
    return list(TOPICS)


def by_key(key: str):
    for t in TOPICS:
        if t["key"] == key:
            return t
    return None
