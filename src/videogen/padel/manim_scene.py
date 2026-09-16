"""Escena Manim (Community Edition) — explicación táctica de pádel: EL GLOBO.

Objetivo: CLARIDAD. Campo a escala + jugadores + flecha que se dibuja + zona
resaltada + bola con easing (no lenta) + reacción de los jugadores + etiquetas.
Render vertical 9:16 para Shorts. Se renderiza en CI (apt: cairo/pango/ffmpeg).

    manim -qm -r 1080,1920 manim_scene.py PadelLob
"""
from manim import *
import numpy as np

config.frame_height = 12.0  # con -r 1080,1920 → frame_width ≈ 6.75 (vertical)

# court en metros: cx∈[0,10] ancho, cy∈[0,20] largo (cy=0 abajo/cerca, 20 arriba/lejos)
def pt(cx, cy):
    return np.array([-1.5 + cx / 10.0 * 3.0, -4.5 + cy / 20.0 * 9.0, 0.0])


class PadelLob(Scene):
    def construct(self):
        self.camera.background_color = "#0c1420"

        # ---- CAMPO ----
        court = Polygon(pt(0, 0), pt(10, 0), pt(10, 20), pt(0, 20),
                        stroke_width=0, fill_color="#1f6e8c", fill_opacity=1.0)
        net = Line(pt(0, 10), pt(10, 10), color=WHITE, stroke_width=6)
        serv = VGroup(Line(pt(0, 3), pt(10, 3), color=WHITE, stroke_width=3),
                      Line(pt(0, 17), pt(10, 17), color=WHITE, stroke_width=3),
                      Line(pt(5, 3), pt(5, 17), color=WHITE, stroke_width=3))
        walls = VGroup(*[Line(pt(*a), pt(*b), color="#bfe6f2", stroke_width=8)
                         for a, b in [((0, 0), (10, 0)), ((0, 20), (10, 20)),
                                      ((0, 0), (0, 20)), ((10, 0), (10, 20))]])
        court_g = VGroup(court, walls, serv, net)
        self.play(FadeIn(court_g), run_time=0.7)

        # ---- JUGADORES ----
        def player(cx, cy, color, label):
            dot = Dot(pt(cx, cy), radius=0.24, color=color).set_z_index(3)
            ring = Circle(radius=0.24, color=WHITE, stroke_width=3).move_to(pt(cx, cy)).set_z_index(3)
            txt = Text(label, font_size=22, color=WHITE, weight=BOLD).move_to(pt(cx, cy)).set_z_index(4)
            return VGroup(dot, ring, txt)

        red1 = player(3.5, 8.0, RED, "R")   # rivales en la red
        red2 = player(6.5, 8.5, RED, "R")
        blue1 = player(3.0, 17.0, BLUE, "YOU")  # tú, defendiendo el fondo
        blue2 = player(7.0, 17.0, BLUE, "YOU")
        self.play(*[FadeIn(p) for p in (red1, red2, blue1, blue2)], run_time=0.6)

        lab = Text("Pinned at the back?", font_size=40, color=YELLOW, weight=BOLD).to_edge(UP, buff=0.4)
        self.play(FadeIn(lab, shift=DOWN * 0.3))
        self.wait(0.5)

        # ---- LA JUGADA: globo de blue1 sobre los rojos al fondo rival ----
        start, end = pt(3.0, 16.5), pt(3.3, 2.4)
        arc = ArcBetweenPoints(start, end, angle=-TAU / 5, color=YELLOW, stroke_width=7)
        self.play(Transform(lab, Text("Lob deep to the glass", font_size=40, color=YELLOW, weight=BOLD).to_edge(UP, buff=0.4)))
        self.play(Create(arc), run_time=1.0)

        zone = Circle(radius=0.85, stroke_color=YELLOW, stroke_width=4,
                      fill_color=YELLOW, fill_opacity=0.18).move_to(end)
        self.play(FadeIn(zone), Flash(end, color=YELLOW, line_length=0.3))

        ball = Dot(start, radius=0.16, color="#e8ff2a").set_z_index(6)
        self.add(ball)
        self.play(MoveAlongPath(ball, arc),
                  rate_func=rate_functions.ease_in_out_sine, run_time=1.2)
        self.play(Flash(end, color=WHITE, line_length=0.25),
                  ball.animate.move_to(pt(3.6, 5.0)), rate_func=rush_from, run_time=0.4)
        self.wait(0.3)

        # ---- REACCIÓN: rojos retroceden, tú subes a la red ----
        self.play(
            red1.animate.move_to(pt(3.5, 4.2)), red2.animate.move_to(pt(6.5, 4.6)),
            blue1.animate.move_to(pt(3.0, 12.0)), blue2.animate.move_to(pt(7.0, 12.0)),
            FadeOut(ball), run_time=1.2)
        self.play(Transform(lab, Text("Now YOU take the net", font_size=44, color=GREEN, weight=BOLD).to_edge(UP, buff=0.4)),
                  Indicate(VGroup(blue1, blue2), color=GREEN))
        self.wait(1.4)
