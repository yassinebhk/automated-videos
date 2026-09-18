"""Escenas Manim (CE) — tácticas de pádel. Prioridad: CLARIDAD + explicación.

Formato GANADOR (aprobado 18/09): pista 9:16 que llena la pantalla, TÚ (azul) abajo,
rivales (rojo/R) en la red, bola rápida con estela y rebote visible en cristal, beat
de ERROR con ✗, y tarjeta de cierre opaca con CTA. Narración didáctica (voz aparte).

Cada táctica es una Scene. El registro TACTICS (abajo) mapea key -> escena + narración.

    manim -qm manim_scene.py PadelLob
"""
from manim import *
import numpy as np

config.frame_width = 9.0
config.frame_height = 16.0
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_rate = 30

COURT_BG = "#0c1420"
COURT_FILL = "#1f6e8c"
GLASS = "#bfe6f2"
BALL_C = "#e8ff2a"
TRAIL_C = "#fff59d"


def pt(cx, cy):
    """Pista lógica 10x20 -> coords de frame 9:16."""
    return np.array([-3.5 + cx / 10.0 * 7.0, -7.0 + cy / 20.0 * 13.2, 0.0])


class PadelBase(Scene):
    """Helpers compartidos: pista, jugadores, título, bola, rebote, cierre."""

    def setup_court(self, you=((3.3, 3.0), (6.7, 3.0)), red=((3.5, 12.0), (6.5, 12.5))):
        self.camera.background_color = COURT_BG
        court = Polygon(pt(0, 0), pt(10, 0), pt(10, 20), pt(0, 20),
                        stroke_width=0, fill_color=COURT_FILL, fill_opacity=1.0)
        net = Line(pt(0, 10), pt(10, 10), color=WHITE, stroke_width=9)
        serv = VGroup(Line(pt(0, 3), pt(10, 3), color=WHITE, stroke_width=5),
                      Line(pt(0, 17), pt(10, 17), color=WHITE, stroke_width=5),
                      Line(pt(5, 3), pt(5, 17), color=WHITE, stroke_width=5))
        walls = VGroup(*[Line(pt(*a), pt(*b), color=GLASS, stroke_width=11)
                         for a, b in [((0, 0), (10, 0)), ((0, 20), (10, 20)),
                                      ((0, 0), (0, 20)), ((10, 0), (10, 20))]])
        self.play(FadeIn(VGroup(court, walls, serv, net)), run_time=0.5)
        self.blues = [self._player(cx, cy, BLUE, "YOU") for cx, cy in you]
        self.reds = [self._player(cx, cy, RED, "R") for cx, cy in red]
        self.play(*[FadeIn(p) for p in self.blues + self.reds], run_time=0.5)
        self.lab = None

    @staticmethod
    def _player(cx, cy, color, label):
        dot = Dot(pt(cx, cy), radius=0.42, color=color).set_z_index(3)
        ring = Circle(radius=0.42, color=WHITE, stroke_width=5).move_to(pt(cx, cy)).set_z_index(3)
        txt = Text(label, font_size=26, color=WHITE, weight=BOLD).move_to(pt(cx, cy)).set_z_index(4)
        return VGroup(dot, ring, txt)

    @staticmethod
    def _title(text, color=YELLOW):
        t = Text(text, font_size=56, color=color, weight=BOLD)
        if t.width > 8.4:
            t.scale_to_fit_width(8.4)
        return t.to_edge(UP, buff=0.35)

    def show_title(self, text, color=YELLOW, run_time=0.5):
        t = self._title(text, color)
        if self.lab is None:
            self.play(FadeIn(t, shift=DOWN * 0.3), run_time=run_time)
            self.lab = t
        else:
            self.play(Transform(self.lab, t), run_time=run_time)

    def add_ball(self, start, radius=0.30):
        ball = Dot(start, radius=radius, color=BALL_C).set_z_index(6)
        trail = TracedPath(ball.get_center, stroke_color=TRAIL_C,
                           stroke_width=7, dissipating_time=0.45)
        self.add(trail, ball)
        return ball, trail

    def target_zone(self, center, radius=1.05, color=YELLOW):
        return Circle(radius=radius, stroke_color=color, stroke_width=5,
                      fill_color=color, fill_opacity=0.16).move_to(center)

    def glass_bounce(self, point, glow_a, glow_b, label, label_ref):
        wall_glow = Line(pt(*glow_a), pt(*glow_b), color=YELLOW, stroke_width=16).set_z_index(2)
        bl = Text(label, font_size=40, color=YELLOW, weight=BOLD).next_to(label_ref, DOWN, buff=0.2)
        self.play(Flash(point, color=WHITE, line_length=0.9, num_lines=16),
                  FadeIn(wall_glow, rate_func=there_and_back),
                  FadeIn(bl, scale=1.2), run_time=0.5)
        return bl

    def error_cross(self, at, run_time=0.5):
        x = Cross(scale_factor=0.55, stroke_color=RED, stroke_width=12).move_to(at).set_z_index(7)
        self.play(Flash(at, color=RED, line_length=0.6, num_lines=14), Create(x), run_time=run_time)
        return x

    def outro(self, recap_text, cta_text="▶  FOLLOW FOR MORE\nPADEL TACTICS", hold=3.0):
        panel = Rectangle(width=9.4, height=16.4, fill_color=COURT_BG,
                          fill_opacity=1.0, stroke_width=0).set_z_index(20)
        ball_icon = VGroup(
            Dot(radius=0.5, color=BALL_C),
            Arc(radius=0.5, start_angle=PI * 0.15, angle=PI * 0.7, color=COURT_BG, stroke_width=5),
            Arc(radius=0.5, start_angle=PI * 1.15, angle=PI * 0.7, color=COURT_BG, stroke_width=5),
        ).move_to(UP * 5.4).set_z_index(21)
        recap = Text(recap_text, font_size=58, color=GREEN, weight=BOLD,
                     line_spacing=1.1, should_center=True).set_z_index(21)
        if recap.width > 8.0:
            recap.scale_to_fit_width(8.0)
        recap.move_to(UP * 1.2)
        cta = Text(cta_text, font_size=48, color=YELLOW, weight=BOLD,
                   line_spacing=1.15, should_center=True).set_z_index(21)
        if cta.width > 7.6:
            cta.scale_to_fit_width(7.6)
        cta.next_to(recap, DOWN, buff=1.3)
        anims = [FadeIn(panel)]
        if self.lab is not None:
            anims.append(FadeOut(self.lab))
        self.play(*anims, run_time=0.4)
        self.play(FadeIn(ball_icon, scale=0.6), Write(recap), run_time=0.9)
        self.play(FadeIn(cta, shift=UP * 0.3), run_time=0.6)
        self.wait(hold)


# ══════════════════════════ 1) EL GLOBO (lob) ══════════════════════════
class PadelLob(PadelBase):
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

    def construct(self):
        self.setup_court()
        self.show_title("They own the net")
        self.wait(3.0)

        self.show_title("Don't force it", color=RED)
        force = ArcBetweenPoints(pt(5, 3.6), pt(5, 10.6), angle=TAU / 18, color="#c9d3dd", stroke_width=9)
        self.play(Create(force), run_time=0.5)
        x = self.error_cross(pt(5, 10.8))
        self.wait(1.9)
        self.play(FadeOut(force), FadeOut(x), run_time=0.3)

        self.show_title("Play the LOB", color=YELLOW)
        self.wait(1.2)
        start, land, after = pt(3.3, 3.6), pt(3.5, 19.5), pt(5.4, 15.8)
        arc1 = ArcBetweenPoints(start, land, angle=TAU / 7, color=YELLOW, stroke_width=10)
        arc2 = ArcBetweenPoints(land, after, angle=-TAU / 6, color=YELLOW, stroke_width=9)
        self.play(Create(arc1), run_time=0.6)
        zone = self.target_zone(pt(3.5, 18.2))
        self.play(FadeIn(zone), run_time=0.3)
        ball, trail = self.add_ball(start)
        self.play(MoveAlongPath(ball, arc1), rate_func=linear, run_time=0.85)
        bl = self.glass_bounce(land, (1.5, 20), (5.5, 20), "Off the glass!", zone)
        self.play(Create(arc2), MoveAlongPath(ball, arc2), rate_func=rush_from, run_time=0.6)
        self.wait(0.9)
        self.play(FadeOut(bl), run_time=0.2)

        self.show_title("They retreat", color=ORANGE)
        self.play(self.reds[0].animate.move_to(pt(3.5, 16.5)), self.reds[1].animate.move_to(pt(6.5, 16.9)),
                  FadeOut(ball), FadeOut(trail), FadeOut(zone), FadeOut(arc1), FadeOut(arc2), run_time=1.1)
        self.wait(1.8)

        self.play(self.blues[0].animate.move_to(pt(3.3, 8.5)), self.blues[1].animate.move_to(pt(6.7, 8.5)),
                  Transform(self.lab, self._title("You take the net", color=GREEN)), run_time=1.0)
        self.play(Indicate(VGroup(*self.blues), color=GREEN, scale_factor=1.25), run_time=0.6)
        self.wait(2.0)
        self.outro("Control the net\n=\ncontrol the point")


# ══════════════════════════ 2) BAJADA DE PARED (back_wall) ══════════════════════════
class PadelBackWall(PadelBase):
    NARRATION = (
        "A ball flying at your back glass, and you panic and swing early? "
        "That's how you spray it into the net. "
        "Let it come. Let the ball pass you, hit the back wall, and bounce back out. "
        "Now, with the rebound sitting in front of you, stay low, and lift it. "
        "A deep, high lob back to their side. "
        "You just turned a defensive ball into a clean reset, and you're still in the point. "
        "Follow for more padel tactics."
    )

    def construct(self):
        self.setup_court(you=((5.0, 5.0), (7.5, 6.0)), red=((3.5, 13.5), (6.5, 13.5)))
        self.show_title("Ball off your back wall")
        # bola entrante hacia el fondo (detras del jugador)
        inc = ArcBetweenPoints(pt(5.0, 12.0), pt(5.0, 1.0), angle=-TAU / 16, color=YELLOW, stroke_width=9)
        self.play(Create(inc), run_time=0.5)
        ball, trail = self.add_ball(pt(5.0, 12.0))
        self.play(MoveAlongPath(ball, inc), rate_func=linear, run_time=0.9)
        self.wait(0.6)

        # ERROR: golpear antes de la pared
        self.show_title("Don't swing early", color=RED)
        x = self.error_cross(pt(5.0, 4.0))
        self.wait(2.0)
        self.play(FadeOut(x), FadeOut(inc), run_time=0.3)

        # SOLUCION: dejar que rebote en la pared y sale
        self.show_title("Let the wall work", color=YELLOW)
        reb = ArcBetweenPoints(pt(5.0, 1.0), pt(5.0, 6.5), angle=TAU / 14, color=YELLOW, stroke_width=9)
        bl = self.glass_bounce(pt(5.0, 0.4), (3.0, 0), (7.0, 0), "Off the back wall", self.blues[0])
        self.play(Create(reb), MoveAlongPath(ball, reb), rate_func=rush_from, run_time=0.7)
        self.play(FadeOut(bl), run_time=0.2)
        self.wait(1.6)

        # lob profundo de vuelta
        self.show_title("Lift a deep lob", color=GREEN)
        lob = ArcBetweenPoints(pt(5.0, 6.5), pt(5.5, 18.5), angle=TAU / 8, color=GREEN, stroke_width=10)
        zone = self.target_zone(pt(5.5, 18.0), color=GREEN)
        self.play(FadeIn(zone), run_time=0.3)
        self.play(Create(lob), MoveAlongPath(ball, lob), rate_func=linear, run_time=1.0)
        self.play(Indicate(zone, color=GREEN, scale_factor=1.2), run_time=0.6)
        self.wait(1.8)
        self.outro("Defense into\na clean reset")


# ══════════════════════════ 3) LA BANDEJA (bandeja) ══════════════════════════
class PadelBandeja(PadelBase):
    NARRATION = (
        "They lob you, and you go for the big flat smash? "
        "Miss it, and you've handed them the net. "
        "Don't. Play the bandeja. "
        "It's a controlled, slicing overhead. Hit it out in front of you, "
        "aim it cross-court and deep, and keep it low over the net. "
        "You won't win the point with it, but you keep your position at the net, and you stay in control. "
        "Follow for more padel tactics."
    )

    def construct(self):
        self.setup_court(you=((3.3, 8.5), (6.7, 8.5)), red=((3.5, 12.0), (6.5, 12.5)))
        self.show_title("They lob you")
        # globo rival por encima de ti
        lob_in = ArcBetweenPoints(pt(4.0, 12.0), pt(3.5, 5.0), angle=-TAU / 8, color="#c9d3dd", stroke_width=8)
        self.play(Create(lob_in), run_time=0.6)
        ball, trail = self.add_ball(pt(4.0, 12.0))
        self.play(MoveAlongPath(ball, lob_in), rate_func=linear, run_time=0.9)
        self.wait(0.8)

        # ERROR: remate plano arriesgado
        self.show_title("Not the big smash", color=RED)
        flat = ArcBetweenPoints(pt(3.5, 6.0), pt(7.0, 19.0), angle=TAU / 20, color="#c9d3dd", stroke_width=7)
        self.play(Create(flat), run_time=0.4)
        x = self.error_cross(pt(7.0, 19.0))
        self.wait(1.8)
        self.play(FadeOut(x), FadeOut(flat), FadeOut(lob_in), run_time=0.3)

        # SOLUCION: bandeja cruzada, controlada, baja y profunda
        self.show_title("Play the BANDEJA", color=YELLOW)
        band = ArcBetweenPoints(pt(3.5, 6.0), pt(7.5, 17.5), angle=TAU / 12, color=YELLOW, stroke_width=10)
        zone = self.target_zone(pt(7.5, 17.2))
        self.play(FadeIn(zone), run_time=0.3)
        self.play(Create(band), MoveAlongPath(ball, band), rate_func=linear, run_time=1.0)
        self.wait(1.6)

        # te QUEDAS en la red
        self.show_title("Keep the net", color=GREEN)
        self.play(Indicate(VGroup(*self.blues), color=GREEN, scale_factor=1.2), run_time=0.6)
        self.wait(2.2)
        self.outro("Stay in control\nat the net")


# ══════════════════════════ 4) REMATE POR TRES (smash) ══════════════════════════
class PadelSmash(PadelBase):
    NARRATION = (
        "Got a short, high ball sitting up at the net? "
        "This is your moment to finish the point. "
        "Hit down, hard, into the corner. "
        "The ball smashes into the floor, rockets up off the back glass, "
        "and flies out over the side fence. "
        "That's the por tres, and it's impossible to return. "
        "But only go for it when the ball is high and short. "
        "Follow for more padel tactics."
    )

    def construct(self):
        self.setup_court(you=((3.3, 8.5), (6.7, 8.5)), red=((3.5, 15.0), (6.5, 15.5)))
        self.show_title("High and short ball")
        # bola corta y alta que sube
        sit = self.target_zone(pt(4.0, 7.0))
        self.play(FadeIn(sit), run_time=0.3)
        ball, trail = self.add_ball(pt(4.0, 7.0))
        self.wait(1.6)

        self.show_title("SMASH it down", color=YELLOW)
        # remate hacia abajo al fondo
        down = ArcBetweenPoints(pt(4.0, 7.0), pt(4.0, 19.4), angle=-TAU / 30, color=YELLOW, stroke_width=11)
        self.play(Create(down), MoveAlongPath(ball, down), rate_func=rush_into, run_time=0.55)
        bl = self.glass_bounce(pt(4.0, 19.6), (2.0, 20), (6.0, 20), "Off the glass!", self.reds[0])
        self.wait(0.4)
        self.play(FadeOut(bl), run_time=0.2)

        # sube MUY alto por el cristal y sale por la valla lateral
        self.show_title("...and OUT! Por tres", color=GREEN)
        up = ArcBetweenPoints(pt(4.0, 19.4), pt(16.0, 12.0), angle=-TAU / 6, color=GREEN, stroke_width=10)
        self.play(Create(up), MoveAlongPath(ball, up), rate_func=linear, run_time=0.9)
        out_lab = Text("Unreturnable!", font_size=44, color=GREEN, weight=BOLD).move_to(pt(7.0, 8.0))
        if out_lab.width > 8.0:
            out_lab.scale_to_fit_width(8.0)
        self.play(FadeIn(out_lab, scale=1.2), run_time=0.5)
        self.wait(1.8)
        self.play(FadeOut(out_lab), run_time=0.2)
        self.outro("Only when it's\nhigh and short")


# ══════════════════════════ 5) LA DEJADA (drop_shot) ══════════════════════════
class PadelDrop(PadelBase):
    NARRATION = (
        "Both rivals pinned deep at the back glass? "
        "Don't just keep hitting hard straight into them. "
        "Surprise them. Take all the pace off, "
        "and drop it soft, just over the net, so it dies before they can sprint in. "
        "The deeper they hang back, the deadlier the drop shot becomes. "
        "Disguise it like a normal shot until the very last moment. "
        "Follow for more padel tactics."
    )

    def construct(self):
        self.setup_court(you=((3.3, 8.5), (6.7, 8.5)), red=((3.5, 18.0), (6.5, 18.2)))
        self.show_title("They're deep at the back")
        self.play(Indicate(VGroup(*self.reds), color=RED, scale_factor=1.15), run_time=0.6)
        self.wait(1.8)

        # ERROR: pegar fuerte hacia ellos
        self.show_title("Don't hit into them", color=RED)
        hard = ArcBetweenPoints(pt(4.0, 9.0), pt(3.8, 17.5), angle=TAU / 22, color="#c9d3dd", stroke_width=8)
        self.play(Create(hard), run_time=0.4)
        x = self.error_cross(pt(3.8, 17.5))
        self.wait(1.7)
        self.play(FadeOut(x), FadeOut(hard), run_time=0.3)

        # SOLUCION: dejada suave que muere en la red
        self.show_title("Drop it SOFT", color=YELLOW)
        drop = ArcBetweenPoints(pt(4.0, 9.0), pt(4.2, 11.2), angle=TAU / 5, color=YELLOW, stroke_width=10)
        zone = self.target_zone(pt(4.2, 11.2), radius=0.85)
        self.play(FadeIn(zone), run_time=0.3)
        ball, trail = self.add_ball(pt(4.0, 9.0))
        self.play(Create(drop), MoveAlongPath(ball, drop), rate_func=rush_from, run_time=1.1)
        die = Text("...it dies here", font_size=38, color=YELLOW, weight=BOLD).next_to(zone, DOWN, buff=0.25)
        self.play(FadeIn(die), run_time=0.4)
        self.wait(1.6)
        self.play(FadeOut(die), run_time=0.2)

        self.show_title("Too far to reach", color=GREEN)
        self.wait(2.0)
        self.outro("The deeper they are,\nthe deadlier the drop")


# ══════════════════════════ 6) EL SAQUE (serve) ══════════════════════════
class PadelServe(PadelBase):
    NARRATION = (
        "Wasting your serve by tapping it flat down the middle? "
        "The serve sets up the entire point. "
        "Serve underhand, below your waist, and aim it out wide, "
        "into the corner, so it kicks off the side glass and drags your rival off the court. "
        "Then step in immediately and take the net. "
        "A smart serve, and you're on the attack from the very first ball. "
        "Follow for more padel tactics."
    )

    def construct(self):
        self.setup_court(you=((6.5, 3.0), (3.3, 4.0)), red=((3.0, 14.0), (6.5, 13.0)))
        self.show_title("Your serve")
        # ERROR: saque plano al centro
        self.show_title("Not flat to the middle", color=RED)
        mid = ArcBetweenPoints(pt(6.0, 3.4), pt(5.0, 13.0), angle=TAU / 24, color="#c9d3dd", stroke_width=8)
        self.play(Create(mid), run_time=0.4)
        x = self.error_cross(pt(5.0, 13.0))
        self.wait(1.9)
        self.play(FadeOut(x), FadeOut(mid), run_time=0.3)

        # SOLUCION: saque abierto a la esquina, rebota en cristal lateral
        self.show_title("Serve WIDE", color=YELLOW)
        serve = ArcBetweenPoints(pt(6.0, 3.4), pt(1.2, 13.5), angle=-TAU / 16, color=YELLOW, stroke_width=10)
        zone = self.target_zone(pt(1.3, 13.5), radius=0.9)
        self.play(FadeIn(zone), run_time=0.3)
        ball, trail = self.add_ball(pt(6.0, 3.4))
        self.play(Create(serve), MoveAlongPath(ball, serve), rate_func=linear, run_time=0.9)
        bl = self.glass_bounce(pt(0.4, 13.5), (0, 11.5), (0, 15.5), "Kicks off the glass", zone)
        kick = ArcBetweenPoints(pt(0.4, 13.5), pt(-2.0, 15.0), angle=TAU / 12, color=YELLOW, stroke_width=8)
        self.play(Create(kick), MoveAlongPath(ball, kick), rate_func=rush_from, run_time=0.5)
        self.play(FadeOut(bl), run_time=0.2)
        self.wait(1.4)

        # subes a la red
        self.show_title("...and take the net", color=GREEN)
        self.play(self.blues[0].animate.move_to(pt(6.5, 8.5)), self.blues[1].animate.move_to(pt(3.3, 8.5)),
                  run_time=1.0)
        self.play(Indicate(VGroup(*self.blues), color=GREEN, scale_factor=1.2), run_time=0.6)
        self.wait(1.8)
        self.outro("Attack from\nthe first ball")


# ══════════════════════════ 7) POSICIÓN (positioning) ══════════════════════════
class PadelPositioning(PadelBase):
    NARRATION = (
        "Chasing every ball on your own while your partner just watches? "
        "That's a losing team. "
        "In padel, you move as one. "
        "Stay side by side, a few meters apart, and slide together. "
        "Left, right, up and back, like you're tied together by a rope. "
        "Cover the middle, and never leave a gap between you. "
        "Move as a pair, and the court has no holes. "
        "Follow for more padel tactics."
    )

    def construct(self):
        self.setup_court(you=((3.0, 6.0), (7.0, 6.0)), red=((3.5, 14.0), (6.5, 14.0)))
        # cuerda que une a la pareja
        rope = always_redraw(lambda: Line(self.blues[0].get_center(), self.blues[1].get_center(),
                                          color=GREEN, stroke_width=6).set_z_index(2))
        self.show_title("Move as a pair")
        self.add(rope)
        self.play(Indicate(VGroup(*self.blues), color=GREEN, scale_factor=1.15), run_time=0.6)
        self.wait(1.8)

        # ERROR: uno solo persigue, hueco en el medio
        self.show_title("Don't split up", color=RED)
        self.play(self.blues[0].animate.move_to(pt(1.2, 4.0)), run_time=0.8)
        gap = self.error_cross(pt(5.0, 6.0))
        self.wait(1.7)
        self.play(FadeOut(gap), self.blues[0].animate.move_to(pt(3.0, 6.0)), run_time=0.6)

        # SOLUCION: deslizan juntos izq/der/arriba
        self.show_title("Slide TOGETHER", color=YELLOW)
        self.play(self.blues[0].animate.move_to(pt(1.5, 6.0)), self.blues[1].animate.move_to(pt(5.5, 6.0)),
                  run_time=0.9)
        self.play(self.blues[0].animate.move_to(pt(4.5, 6.0)), self.blues[1].animate.move_to(pt(8.5, 6.0)),
                  run_time=0.9)
        self.play(self.blues[0].animate.move_to(pt(3.0, 8.7)), self.blues[1].animate.move_to(pt(7.0, 8.7)),
                  run_time=0.9)
        self.wait(1.0)

        self.show_title("No gaps in the middle", color=GREEN)
        self.play(Indicate(VGroup(*self.blues), color=GREEN, scale_factor=1.2), run_time=0.6)
        self.wait(1.8)
        self.outro("Move as one,\nno holes in the court")


# ══════════════════════════ 8) DEFENSA (defense) ══════════════════════════
class PadelDefense(PadelBase):
    NARRATION = (
        "They're at the net, smashing, and you're getting bombarded? "
        "Don't try to counter-attack from the back. You'll just feed them easy balls. "
        "Defend patiently. Both of you drop back, stay low, and absorb the pressure. "
        "Then lift a high, deep lob to push them off the net "
        "and reset the point back to neutral. "
        "Survive the storm, and the point turns your way. "
        "Follow for more padel tactics."
    )

    def construct(self):
        self.setup_court(you=((3.3, 6.0), (6.7, 6.0)), red=((3.5, 11.0), (6.5, 11.0)))
        self.show_title("They bomb the net")
        # remate rival hacia ti
        smash = ArcBetweenPoints(pt(4.0, 11.0), pt(3.8, 5.0), angle=-TAU / 26, color=RED, stroke_width=9)
        self.play(Create(smash), run_time=0.4)
        ball, trail = self.add_ball(pt(4.0, 11.0))
        self.play(MoveAlongPath(ball, smash), rate_func=rush_into, run_time=0.6)
        self.wait(0.8)

        # ERROR: contraatacar desde el fondo
        self.show_title("Don't counter-attack", color=RED)
        counter = ArcBetweenPoints(pt(3.8, 5.0), pt(4.0, 10.0), angle=TAU / 22, color="#c9d3dd", stroke_width=7)
        self.play(Create(counter), run_time=0.4)
        x = self.error_cross(pt(4.0, 10.0))
        self.wait(1.7)
        self.play(FadeOut(x), FadeOut(counter), FadeOut(smash), run_time=0.3)

        # SOLUCION: retroceder juntos, bajos, absorber
        self.show_title("Drop back & absorb", color=YELLOW)
        self.play(self.blues[0].animate.move_to(pt(3.3, 3.2)), self.blues[1].animate.move_to(pt(6.7, 3.2)),
                  run_time=0.9)
        self.wait(1.4)

        # lob de reseteo profundo
        self.show_title("Reset with a lob", color=GREEN)
        reset = ArcBetweenPoints(pt(4.0, 3.5), pt(5.0, 18.5), angle=TAU / 8, color=GREEN, stroke_width=10)
        zone = self.target_zone(pt(5.0, 18.0), color=GREEN)
        self.play(FadeIn(zone), run_time=0.3)
        self.play(Create(reset), MoveAlongPath(ball, reset), rate_func=linear, run_time=1.0)
        self.play(self.reds[0].animate.move_to(pt(3.5, 15.5)), self.reds[1].animate.move_to(pt(6.5, 15.5)),
                  Indicate(zone, color=GREEN, scale_factor=1.2), run_time=0.9)
        self.wait(1.8)
        self.outro("Survive, then\nturn the point")


# ══════════════════════════ PLANTILLAS DATA-DRIVEN ══════════════════════════
# Leen el contenido de la env var PADEL_TOPIC (JSON) → variedad infinita sin
# hand-code. Formatos: fact (curiosidad), compare (material), checklist (tips).

def _load_topic() -> dict:
    import json
    import os as _os
    raw = _os.environ.get("PADEL_TOPIC", "").strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _fit(t, w):
    if t.width > w:
        t.scale_to_fit_width(w)
    return t


class _CardBase(PadelBase):
    """Fondo con pista tenue + pelota motif arriba. Base de las plantillas."""

    def card_bg(self, kicker: str, kicker_color=YELLOW):
        self.camera.background_color = COURT_BG
        # pista muy tenue de fondo (marca de agua)
        court = Polygon(pt(0, 0), pt(10, 0), pt(10, 20), pt(0, 20),
                        stroke_color=GLASS, stroke_width=3, fill_opacity=0.0).set_opacity(0.18)
        net = Line(pt(0, 10), pt(10, 10), color=GLASS, stroke_width=3).set_opacity(0.18)
        self.add(court, net)
        ball = VGroup(
            Dot(radius=0.5, color=BALL_C),
            Arc(radius=0.5, start_angle=PI * 0.15, angle=PI * 0.7, color=COURT_BG, stroke_width=5),
            Arc(radius=0.5, start_angle=PI * 1.15, angle=PI * 0.7, color=COURT_BG, stroke_width=5),
        ).to_edge(UP, buff=0.7)
        k = _fit(Text(kicker, font_size=40, color=kicker_color, weight=BOLD), 7.8)
        k.next_to(ball, DOWN, buff=0.35)
        self.play(FadeIn(ball, scale=0.6), FadeIn(k, shift=DOWN * 0.2), run_time=0.6)
        self.lab = None
        return VGroup(ball, k)


class PadelFact(_CardBase):
    """Curiosidad / '¿Sabías que?'. Topic: {kicker,title,lines[],punch}."""
    DEFAULT = {
        "kicker": "DID YOU KNOW?",
        "title": "Padel was born\nin a backyard",
        "lines": ["Invented in 1969 in Acapulco, Mexico",
                  "By Enrique Corcuera — no room for a tennis court",
                  "So he walled in a smaller one"],
        "punch": "Now played in 90+ countries",
    }
    NARRATION = ("Here's something most players don't know. "
                 "Padel was invented back in 1969, in Acapulco, Mexico. "
                 "A man named Enrique Corcuera didn't have room for a full tennis court, "
                 "so he built a smaller one and walled it in. "
                 "That backyard experiment is now played in over ninety countries. "
                 "Follow for more padel.")

    def construct(self):
        d = _load_topic() or self.DEFAULT
        self.card_bg(d.get("kicker", "DID YOU KNOW?"))
        title = Text(d.get("title", ""), font_size=58, color=WHITE, weight=BOLD,
                     line_spacing=1.05, should_center=True)
        _fit(title, 8.0).move_to(UP * 3.2)
        self.play(Write(title), run_time=0.8)
        rows = VGroup()
        for i, ln in enumerate(d.get("lines", [])[:3]):
            dot = Dot(radius=0.13, color=BALL_C)
            txt = _fit(Text(ln, font_size=34, color="#d7e3ee"), 6.9)
            row = VGroup(dot, txt).arrange(RIGHT, buff=0.3)
            rows.add(row)
        rows.arrange(DOWN, buff=0.7, aligned_edge=LEFT).move_to(DOWN * 0.5)
        for row in rows:
            self.play(FadeIn(row, shift=RIGHT * 0.3), run_time=0.6)
            self.wait(1.7)
        self.outro(d.get("punch", ""), cta_text="▶  FOLLOW FOR MORE\nPADEL", hold=2.6)


class PadelCompare(_CardBase):
    """Comparativa de material. Topic: {kicker,title,items:[{name,shape}],
    attrs:[{label,values:[..]}]} (values 0-100, uno por item)."""
    DEFAULT = {
        "kicker": "WHICH RACKET?",
        "title": "Round vs Teardrop vs Diamond",
        "items": [{"name": "ROUND", "shape": "round"},
                  {"name": "TEARDROP", "shape": "teardrop"},
                  {"name": "DIAMOND", "shape": "diamond"}],
        "attrs": [{"label": "Control", "values": [95, 70, 45]},
                  {"label": "Power", "values": [45, 70, 95]},
                  {"label": "Forgiveness", "values": [95, 65, 40]}],
        "punch": "Round = control\nDiamond = power",
    }
    NARRATION = ("Round, teardrop, or diamond — which padel racket should you use? "
                 "It comes down to where the weight sits. "
                 "A round racket keeps the sweet spot low and central. "
                 "Maximum control and very forgiving — perfect while you're learning. "
                 "A diamond pushes the weight up high. "
                 "Big power, but far less forgiving — that's a racket for advanced players. "
                 "And the teardrop sits right in between, balanced for improving players. "
                 "Follow for more padel.")
    COLORS = ["#4fc3f7", "#ffd54f", "#ff7043"]

    def _shape(self, kind, color):
        if kind == "diamond":
            head = Square(side_length=1.5, color=color, fill_opacity=0.85,
                          stroke_color=WHITE, stroke_width=3).rotate(PI / 4)
        elif kind == "teardrop":
            head = Ellipse(width=1.35, height=1.95, color=color, fill_opacity=0.85,
                           stroke_color=WHITE, stroke_width=3)
        else:
            head = Circle(radius=0.95, color=color, fill_opacity=0.85,
                          stroke_color=WHITE, stroke_width=3)
        handle = Rectangle(width=0.32, height=0.8, color=color, fill_opacity=0.85,
                           stroke_color=WHITE, stroke_width=2)
        handle.next_to(head, DOWN, buff=0.0)
        return VGroup(head, handle)

    def construct(self):
        d = _load_topic() or self.DEFAULT
        self.card_bg(d.get("kicker", "WHICH RACKET?"))
        title = _fit(Text(d.get("title", ""), font_size=46, color=WHITE, weight=BOLD), 8.0)
        title.move_to(UP * 3.6)
        self.play(Write(title), run_time=0.7)
        items = d.get("items", [])[:3]
        attrs = d.get("attrs", [])[:3]
        for idx, it in enumerate(items):
            color = self.COLORS[idx % 3]
            shape = self._shape(it.get("shape", "round"), color).move_to(UP * 1.4)
            name = _fit(Text(it.get("name", ""), font_size=40, color=color, weight=BOLD), 6.0)
            name.next_to(shape, DOWN, buff=0.35)
            self.play(FadeIn(shape, scale=0.7), FadeIn(name), run_time=0.5)
            bars = VGroup()
            for a in attrs:
                val = (a.get("values", [50, 50, 50])[idx]) / 100.0
                lab = Text(a.get("label", ""), font_size=28, color="#d7e3ee")
                track = RoundedRectangle(width=4.2, height=0.42, corner_radius=0.2,
                                         stroke_color="#33465a", stroke_width=2, fill_opacity=0.0)
                fill = RoundedRectangle(width=max(0.42, 4.2 * val), height=0.42, corner_radius=0.2,
                                        stroke_width=0, fill_color=color, fill_opacity=0.95)
                fill.align_to(track, LEFT)
                bargrp = VGroup(lab, VGroup(track, fill))
                lab.next_to(track, LEFT, buff=0.3)
                bars.add(VGroup(lab, track, fill))
            bars.arrange(DOWN, buff=0.45).move_to(DOWN * 2.2)
            # anima relleno de barras creciendo desde la izquierda
            self.play(*[GrowFromEdge(g[2], LEFT) for g in bars],
                      *[FadeIn(g[0]) for g in bars], *[Create(g[1]) for g in bars],
                      run_time=0.7)
            self.wait(1.8)
            if idx < len(items) - 1:
                self.play(FadeOut(shape), FadeOut(name), FadeOut(bars), run_time=0.35)
        self.outro(d.get("punch", ""), cta_text="▶  FOLLOW FOR MORE\nPADEL", hold=2.4)


class PadelChecklist(_CardBase):
    """Recomendaciones / errores. Topic: {kicker,title,tips:[..],punch}."""
    DEFAULT = {
        "kicker": "BEGINNER FIXES",
        "title": "3 mistakes killing\nyour game",
        "tips": ["Stop smashing everything — control beats power",
                 "Get out of no man's land — net or back, never the middle",
                 "Use the walls — let the ball rebound, don't fear it"],
        "punch": "Fix these and you'll\njump a level fast",
    }
    NARRATION = ("Three mistakes that are quietly killing your padel game. "
                 "Number one: you smash everything. In padel, control beats power almost every time. "
                 "Number two: you're stuck in no man's land. Be at the net, or at the back — never frozen in the middle. "
                 "And number three: you're scared of the walls. Let the ball rebound and play it off the glass. "
                 "Fix these three, and you'll jump a level fast. "
                 "Follow for more padel.")

    def construct(self):
        d = _load_topic() or self.DEFAULT
        self.card_bg(d.get("kicker", "TIPS"))
        title = Text(d.get("title", ""), font_size=52, color=WHITE, weight=BOLD,
                     line_spacing=1.05, should_center=True)
        _fit(title, 8.0).move_to(UP * 3.3)
        self.play(Write(title), run_time=0.8)
        rows = VGroup()
        for i, tip in enumerate(d.get("tips", [])[:4], start=1):
            num = Text(str(i), font_size=40, color=COURT_BG, weight=BOLD).set_z_index(2)
            badge = Circle(radius=0.42, color=BALL_C, fill_opacity=1.0, stroke_width=0)
            num.move_to(badge)
            txt = _fit(Text(tip, font_size=30, color="#d7e3ee"), 6.3)
            row = VGroup(VGroup(badge, num), txt).arrange(RIGHT, buff=0.35)
            rows.add(row)
        rows.arrange(DOWN, buff=0.6, aligned_edge=LEFT).move_to(DOWN * 0.7)
        for row in rows:
            self.play(FadeIn(row, shift=RIGHT * 0.3), run_time=0.55)
            self.wait(1.9)
        self.outro(d.get("punch", ""), cta_text="▶  FOLLOW FOR MORE\nPADEL", hold=2.4)


FORMAT_SCENES = {"fact": "PadelFact", "compare": "PadelCompare", "checklist": "PadelChecklist"}


# ══════════════════════════ REGISTRO ══════════════════════════
# key -> escena Manim + narración + hashtags específicos. Rota en pipeline.
TACTICS = {
    "lob":         {"scene": "PadelLob",         "title": "The Deep Lob",         "es": "El Globo"},
    "back_wall":   {"scene": "PadelBackWall",    "title": "Off the Back Wall",    "es": "Bajada de Pared"},
    "bandeja":     {"scene": "PadelBandeja",     "title": "The Bandeja",          "es": "La Bandeja"},
    "smash":       {"scene": "PadelSmash",       "title": "The 'Por Tres' Smash", "es": "Remate por Tres"},
    "drop_shot":   {"scene": "PadelDrop",        "title": "The Drop Shot",        "es": "La Dejada"},
    "serve":       {"scene": "PadelServe",       "title": "The Smart Serve",      "es": "El Saque"},
    "positioning": {"scene": "PadelPositioning", "title": "Move as a Pair",       "es": "Posición"},
    "defense":     {"scene": "PadelDefense",     "title": "Patient Defense",      "es": "Defensa"},
}


def narration_for(scene_name: str) -> str:
    return globals()[scene_name].NARRATION
