"""Escena Manim (CE) — táctica de pádel: EL GLOBO. Prioridad: CLARIDAD.

Orientación: TÚ (azul) abajo (tu lado, cerca) · rivales (rojo) en la red.
Jugada: globo por encima de los rojos al fondo → ellos retroceden → tú subes a la red.
Campo a escala que llena el 9:16 + flecha que se dibuja + zona resaltada + bola con
easing + jugadores que reaccionan + etiquetas legibles. Render en CI.

    manim -qm manim_scene.py PadelLob
"""
from manim import *
import numpy as np

config.frame_width = 9.0
config.frame_height = 16.0
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_rate = 30

# court metros: cx∈[0,10] ancho, cy∈[0,20] largo. cy=0 abajo (tu fondo), cy=20 arriba.
# Deja margen arriba (1.8) para el título. x±3.5, y de -7 a +6.2.
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
        court_g = VGroup(court, walls, serv, net)
        self.play(FadeIn(court_g), run_time=0.7)

        def player(cx, cy, color, label):
            dot = Dot(pt(cx, cy), radius=0.42, color=color).set_z_index(3)
            ring = Circle(radius=0.42, color=WHITE, stroke_width=5).move_to(pt(cx, cy)).set_z_index(3)
            txt = Text(label, font_size=26, color=WHITE, weight=BOLD).move_to(pt(cx, cy)).set_z_index(4)
            return VGroup(dot, ring, txt)

        # TÚ abajo (fondo cercano), rivales en la red
        blue1 = player(3.3, 3.0, BLUE, "YOU")
        blue2 = player(6.7, 3.0, BLUE, "YOU")
        red1 = player(3.5, 12.0, RED, "R")
        red2 = player(6.5, 12.5, RED, "R")
        self.play(*[FadeIn(p) for p in (blue1, blue2, red1, red2)], run_time=0.6)

        def title(text, color=YELLOW):
            t = Text(text, font_size=56, color=color, weight=BOLD)
            if t.width > 8.4:
                t.scale_to_fit_width(8.4)
            return t.to_edge(UP, buff=0.35)

        lab = title("Pinned at the back?")
        self.play(FadeIn(lab, shift=DOWN * 0.3)); self.wait(0.6)

        # globo: de un YOU (abajo) por encima de los rojos al fondo rival (arriba)
        start, end = pt(3.3, 3.6), pt(3.4, 18.0)
        arc = ArcBetweenPoints(start, end, angle=TAU / 6, color=YELLOW, stroke_width=10)
        self.play(Transform(lab, title("Lob deep over them")))
        self.play(Create(arc), run_time=1.0)

        zone = Circle(radius=1.4, stroke_color=YELLOW, stroke_width=5,
                      fill_color=YELLOW, fill_opacity=0.18).move_to(end)
        self.play(FadeIn(zone), Flash(end, color=YELLOW, line_length=0.5))

        ball = Dot(start, radius=0.28, color="#e8ff2a").set_z_index(6)
        self.add(ball)
        self.play(MoveAlongPath(ball, arc), rate_func=rate_functions.ease_in_out_sine, run_time=1.2)
        self.play(Flash(end, color=WHITE, line_length=0.4),
                  ball.animate.move_to(pt(3.7, 15.5)), rate_func=rush_from, run_time=0.4)
        self.wait(0.6)

        # rivales retroceden al fondo, tú subes a la red
        self.play(
            red1.animate.move_to(pt(3.5, 16.2)), red2.animate.move_to(pt(6.5, 16.6)),
            blue1.animate.move_to(pt(3.3, 8.5)), blue2.animate.move_to(pt(6.7, 8.5)),
            FadeOut(ball), FadeOut(zone), FadeOut(arc), run_time=1.2)
        self.play(Transform(lab, title("Now YOU take the net", color=GREEN)),
                  Indicate(VGroup(blue1, blue2), color=GREEN, scale_factor=1.3))
        self.wait(1.5)
