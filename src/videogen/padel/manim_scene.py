"""Escena Manim (CE) — táctica de pádel: EL GLOBO. Prioridad: CLARIDAD + explicación.

Orientación: TÚ (azul) abajo · rivales (rojo) en la red.
Flujo didáctico (como los canales de coaching de YT):
  1. Problema: te tienen clavado al fondo, ellos dominan la red.
  2. Error: forzar de plano → volea fácil (✗).
  3. Solución: el GLOBO — alto y profundo por encima, al cristal del fondo.
  4. Rebote visible en el cristal → los rojos retroceden a buscarla.
  5. Tú subes y tomas la red.
  6. CIERRE: tarjeta recap + CTA "Follow for more" (final limpio, no se corta).

    manim -qm manim_scene.py PadelLob
"""
from manim import *
import numpy as np

config.frame_width = 9.0
config.frame_height = 16.0
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_rate = 30

# Narración (voz en-US). La animación va sincronizada con estos "beats". ~26s.
# El workflow genera esta MISMA narración con Edge TTS y la muxea.
NARRATION = (
    "Stuck at the back while they control the net? "
    "Forcing your way through just gives them easy volleys. "
    "So don't. Play the lob. "
    "Take the ball early, and lift it high and deep, over their heads to the back glass. "
    "Now they're forced to turn and chase it down. "
    "And as they retreat, you and your partner step up and take the net. "
    "Control the net, and you control the point. "
    "Follow for more padel tactics."
)


def pt(cx, cy):
    return np.array([-3.5 + cx / 10.0 * 7.0, -7.0 + cy / 20.0 * 13.2, 0.0])


class PadelLob(Scene):
    def construct(self):
        self.camera.background_color = "#0c1420"

        court = Polygon(pt(0, 0), pt(10, 0), pt(10, 20), pt(0, 20),
                        stroke_width=0, fill_color="#1f6e8c", fill_opacity=1.0)
        net = Line(pt(0, 10), pt(10, 10), color=WHITE, stroke_width=9)
        serv = VGroup(Line(pt(0, 3), pt(10, 3), color=WHITE, stroke_width=5),
                      Line(pt(0, 17), pt(10, 17), color=WHITE, stroke_width=5),
                      Line(pt(5, 3), pt(5, 17), color=WHITE, stroke_width=5))
        walls = VGroup(*[Line(pt(*a), pt(*b), color="#bfe6f2", stroke_width=11)
                         for a, b in [((0, 0), (10, 0)), ((0, 20), (10, 20)),
                                      ((0, 0), (0, 20)), ((10, 0), (10, 20))]])
        self.play(FadeIn(VGroup(court, walls, serv, net)), run_time=0.5)

        def player(cx, cy, color, label):
            dot = Dot(pt(cx, cy), radius=0.42, color=color).set_z_index(3)
            ring = Circle(radius=0.42, color=WHITE, stroke_width=5).move_to(pt(cx, cy)).set_z_index(3)
            txt = Text(label, font_size=26, color=WHITE, weight=BOLD).move_to(pt(cx, cy)).set_z_index(4)
            return VGroup(dot, ring, txt)

        blue1 = player(3.3, 3.0, BLUE, "YOU")
        blue2 = player(6.7, 3.0, BLUE, "YOU")
        red1 = player(3.5, 12.0, RED, "R")
        red2 = player(6.5, 12.5, RED, "R")
        self.play(*[FadeIn(p) for p in (blue1, blue2, red1, red2)], run_time=0.5)

        def title(text, color=YELLOW):
            t = Text(text, font_size=56, color=color, weight=BOLD)
            if t.width > 8.4:
                t.scale_to_fit_width(8.4)
            return t.to_edge(UP, buff=0.35)

        # ── 1) PROBLEMA ──────────────────────────────────────────────
        lab = title("They own the net")
        self.play(FadeIn(lab, shift=DOWN * 0.3), run_time=0.5)
        self.wait(3.0)  # "Stuck at the back while they control the net?"

        # ── 2) EL ERROR: forzar de plano → volea fácil (✗) ───────────
        self.play(Transform(lab, title("Don't force it", color=RED)), run_time=0.5)
        force = ArcBetweenPoints(pt(5, 3.6), pt(5, 10.6), angle=TAU / 18,
                                 color="#c9d3dd", stroke_width=9)
        self.play(Create(force), run_time=0.5)
        xmark = Cross(scale_factor=0.55, stroke_color=RED, stroke_width=12).move_to(pt(5, 10.8)).set_z_index(7)
        self.play(Flash(pt(5, 10.8), color=RED, line_length=0.6, num_lines=14),
                  Create(xmark), run_time=0.5)
        self.wait(1.9)  # "Forcing your way through just gives them easy volleys."
        self.play(FadeOut(force), FadeOut(xmark), run_time=0.3)

        # ── 3) LA SOLUCIÓN: EL GLOBO ─────────────────────────────────
        self.play(Transform(lab, title("Play the LOB", color=YELLOW)), run_time=0.5)
        self.wait(1.2)  # "So don't. Play the lob."

        start = pt(3.3, 3.6)
        land = pt(3.5, 19.5)                       # LLEGA AL CRISTAL del fondo
        after = pt(5.4, 15.8)                      # sale rebotado hacia el centro
        arc1 = ArcBetweenPoints(start, land, angle=TAU / 7, color=YELLOW, stroke_width=10)
        arc2 = ArcBetweenPoints(land, after, angle=-TAU / 6, color=YELLOW, stroke_width=9)

        self.play(Create(arc1), run_time=0.6)
        zone = Circle(radius=1.05, stroke_color=YELLOW, stroke_width=5,
                      fill_color=YELLOW, fill_opacity=0.16).move_to(pt(3.5, 18.2))
        self.play(FadeIn(zone), run_time=0.3)

        ball = Dot(start, radius=0.30, color="#e8ff2a").set_z_index(6)
        trail = TracedPath(ball.get_center, stroke_color="#fff59d",
                           stroke_width=7, dissipating_time=0.45)
        self.add(trail, ball)
        self.play(MoveAlongPath(ball, arc1), rate_func=linear, run_time=0.85)  # globo alto y profundo

        # REBOTE VISIBLE: destello + cristal del fondo iluminado + "Off the glass!"
        wall_glow = Line(pt(1.5, 20), pt(5.5, 20), color=YELLOW, stroke_width=16).set_z_index(2)
        bounce_lab = Text("Off the glass!", font_size=40, color=YELLOW, weight=BOLD).next_to(zone, DOWN, buff=0.2)
        self.play(Flash(land, color=WHITE, line_length=0.9, num_lines=16),
                  FadeIn(wall_glow, rate_func=there_and_back),
                  FadeIn(bounce_lab, scale=1.2), run_time=0.5)
        self.play(Create(arc2), MoveAlongPath(ball, arc2), rate_func=rush_from, run_time=0.6)
        self.wait(0.9)  # "...over their heads to the back glass."
        self.play(FadeOut(bounce_lab), run_time=0.2)

        # ── 4) REACCIÓN: rivales retroceden a buscarla ───────────────
        self.play(Transform(lab, title("They retreat", color=ORANGE)),
                  red1.animate.move_to(pt(3.5, 16.5)), red2.animate.move_to(pt(6.5, 16.9)),
                  FadeOut(ball), FadeOut(trail), FadeOut(zone), FadeOut(arc1), FadeOut(arc2),
                  run_time=1.1)
        self.wait(1.8)  # "Now they're forced to turn and chase it down."

        # ── 5) TÚ TOMAS LA RED ───────────────────────────────────────
        self.play(blue1.animate.move_to(pt(3.3, 8.5)), blue2.animate.move_to(pt(6.7, 8.5)),
                  Transform(lab, title("You take the net", color=GREEN)), run_time=1.0)
        self.play(Indicate(VGroup(blue1, blue2), color=GREEN, scale_factor=1.25), run_time=0.6)
        self.wait(2.0)  # "And as they retreat, you and your partner step up and take the net."

        # ── 6) CIERRE: tarjeta recap + CTA (final limpio, no se corta) ─
        panel = Rectangle(width=9.0, height=16.0, fill_color="#0c1420",
                          fill_opacity=0.9, stroke_width=0).set_z_index(20)
        recap = Text("Control the net =\ncontrol the point", font_size=56, color=GREEN,
                     weight=BOLD, line_spacing=1.15, should_center=True).set_z_index(21)
        recap.move_to(UP * 1.6)
        cta = Text("▶  FOLLOW FOR MORE\nPADEL TACTICS", font_size=46, color=YELLOW,
                   weight=BOLD, line_spacing=1.15, should_center=True).set_z_index(21)
        cta.next_to(recap, DOWN, buff=1.0)
        self.play(FadeIn(panel), run_time=0.4)
        self.play(Write(recap), run_time=0.9)
        self.play(FadeIn(cta, shift=UP * 0.3), run_time=0.6)
        self.wait(3.0)  # "Control the net... Follow for more padel tactics." (hold final)
