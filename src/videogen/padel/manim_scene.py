"""Escena Manim (CE) — táctica de pádel: EL GLOBO. Prioridad: CLARIDAD + ritmo.

Orientación: TÚ (azul) abajo · rivales (rojo) en la red.
Jugada: globo RÁPIDO y continuo por encima de los rojos → rebota en el cristal del
fondo → los rojos retroceden → tú subes a la red. Campo a escala que llena el 9:16,
flecha, zona, bola veloz con estela, jugadores que reaccionan, etiquetas legibles.

    manim -qm manim_scene.py PadelLob
"""
from manim import *
import numpy as np

config.frame_width = 9.0
config.frame_height = 16.0
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_rate = 30

# Narración (voz en-US) — se genera aparte y se muxea. La animación va sincronizada
# con estos "beats". ~13s.
NARRATION = ("Pinned at the back while they own the net? Don't force it. "
             "Lob deep over their heads to the back glass. "
             "It pushes them back, and the net is yours.")


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

        lab = title("Pinned at the back?")
        self.play(FadeIn(lab, shift=DOWN * 0.3), run_time=0.5)
        self.wait(1.7)  # beat voz: "Pinned at the back while they own the net? Don't force it."

        # ---- TRAYECTORIA COMPLETA (una sola, continua): globo + REBOTE en cristal ----
        start = pt(3.3, 3.6)
        land = pt(3.5, 19.5)                       # LLEGA AL CRISTAL del fondo
        after = pt(5.4, 15.8)                      # sale rebotado hacia el centro
        arc1 = ArcBetweenPoints(start, land, angle=TAU / 7, color=YELLOW, stroke_width=10)
        arc2 = ArcBetweenPoints(land, after, angle=-TAU / 6, color=YELLOW, stroke_width=9)  # rebote marcado

        self.play(Transform(lab, title("Lob deep over them")), run_time=0.5)
        self.play(Create(arc1), run_time=0.6)

        zone = Circle(radius=1.05, stroke_color=YELLOW, stroke_width=5,
                      fill_color=YELLOW, fill_opacity=0.16).move_to(pt(3.5, 18.2))
        self.play(FadeIn(zone), run_time=0.3)

        # bola veloz con estela recorriendo TODO el arco
        ball = Dot(start, radius=0.30, color="#e8ff2a").set_z_index(6)
        trail = TracedPath(ball.get_center, stroke_color="#fff59d",
                           stroke_width=7, dissipating_time=0.45)
        self.add(trail, ball)
        self.play(MoveAlongPath(ball, arc1), rate_func=linear, run_time=0.7)   # globo rápido hasta el cristal

        # REBOTE VISIBLE: destello + el cristal del fondo se ilumina + "Off the glass!"
        wall_glow = Line(pt(1.5, 20), pt(5.5, 20), color=YELLOW, stroke_width=16).set_z_index(2)
        bounce_lab = Text("Off the glass!", font_size=40, color=YELLOW, weight=BOLD).next_to(zone, DOWN, buff=0.2)
        self.play(Flash(land, color=WHITE, line_length=0.9, num_lines=16),
                  FadeIn(wall_glow, rate_func=there_and_back),
                  FadeIn(bounce_lab, scale=1.2), run_time=0.5)
        self.play(Create(arc2), MoveAlongPath(ball, arc2), rate_func=rush_from, run_time=0.6)  # sale rebotada
        self.play(FadeOut(bounce_lab), run_time=0.2)
        self.wait(0.3)

        # ---- REACCIÓN: rivales retroceden, tú subes a la red ----
        self.play(
            red1.animate.move_to(pt(3.5, 16.5)), red2.animate.move_to(pt(6.5, 16.9)),
            blue1.animate.move_to(pt(3.3, 8.5)), blue2.animate.move_to(pt(6.7, 8.5)),
            FadeOut(ball), FadeOut(trail), FadeOut(zone), FadeOut(arc1), FadeOut(arc2),
            run_time=1.0)
        self.play(Transform(lab, title("Now YOU take the net", color=GREEN)),
                  Indicate(VGroup(blue1, blue2), color=GREEN, scale_factor=1.3), run_time=0.6)
        self.wait(3.6)  # beat voz final: "It pushes them back, and the net is yours." + hold
