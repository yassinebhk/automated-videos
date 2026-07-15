"""Modelos Pydantic compartidos por el pipeline."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScriptSegment(BaseModel):
    """Un segmento del script con su texto y keywords visuales asociadas."""

    text: str
    visual_keywords: list[str] = Field(default_factory=list)
    approx_seconds: float = 0.0


class LocalizedScript(BaseModel):
    """Script completo en un idioma."""

    lang: str  # "es" | "en"
    title: str
    description: str
    hashtags: list[str]
    thumbnail_text: str
    teaser: ScriptSegment | None = None  # cold-open: ráfaga de payoffs (~5s)
    hook: ScriptSegment
    body: list[ScriptSegment]
    cta: ScriptSegment

    def ordered_segments(self) -> list[tuple[str, "ScriptSegment"]]:
        """Segmentos en orden de reproducción con su etiqueta.
        Orden: teaser (si existe) → hook → body[…] → cta."""
        segs: list[tuple[str, ScriptSegment]] = []
        if self.teaser:
            segs.append(("teaser", self.teaser))
        segs.append(("hook", self.hook))
        for i, b in enumerate(self.body):
            segs.append((f"body[{i}]", b))
        segs.append(("cta", self.cta))
        return segs

    def full_text(self) -> str:
        return " ".join(s.text for _, s in self.ordered_segments())

    def all_visual_keywords(self) -> list[str]:
        kws: list[str] = []
        for _, seg in self.ordered_segments():
            kws.extend(seg.visual_keywords)
        return kws


class GeneratedScripts(BaseModel):
    """Resultado de la generación de script bilingüe."""

    slug: str
    topic: str
    music_mood: str = "upbeat"  # epic | medieval | mystery | horror | tech | upbeat | happy | emotional | chill | dramatic
    subject_person: str = ""  # persona pública del topic (para foto CC), "" si no aplica
    es: LocalizedScript
    en: LocalizedScript


class LongChapter(BaseModel):
    """Capítulo de un long-form (~90-120s)."""

    name: str  # título del capítulo (irá en pantalla + en timestamps de YT)
    text: str  # narración del capítulo
    visual_keywords: list[str] = Field(default_factory=list)  # B-roll del capítulo
    approx_seconds: float = 0.0


class LongLocalizedScript(BaseModel):
    """Script long-form en un idioma (intro + capítulos + outro)."""

    lang: str
    title: str
    description: str  # se enriquecerá con timestamps automáticos
    hashtags: list[str]
    thumbnail_text: str
    intro: ScriptSegment  # ~30-45s: hook + tesis del vídeo
    chapters: list[LongChapter]  # 3-5 capítulos de ~90-120s
    outro: ScriptSegment  # ~30-45s: cierre + follow ask obligatorio

    def ordered_segments(self) -> list[tuple[str, ScriptSegment]]:
        segs: list[tuple[str, ScriptSegment]] = [("intro", self.intro)]
        for i, ch in enumerate(self.chapters):
            segs.append((f"chapter[{i}]:{ch.name}", ScriptSegment(
                text=ch.text, visual_keywords=ch.visual_keywords,
                approx_seconds=ch.approx_seconds,
            )))
        segs.append(("outro", self.outro))
        return segs

    def full_text(self) -> str:
        return " ".join(s.text for _, s in self.ordered_segments())


class GeneratedLongScripts(BaseModel):
    """Resultado de la generación de long-form bilingüe."""

    slug: str
    topic: str
    target_minutes: int = 7
    music_mood: str = "tech"
    subject_person: str = ""
    es: LongLocalizedScript
    en: LongLocalizedScript


class TTNativeScript(BaseModel):
    """Guion TT-first (28-34s, 9:16, sin música, comment-bait). Un solo idioma:
    TikTok funciona mejor con foco mono-lingüe que con doblajes paralelos."""

    slug: str
    topic: str
    format: str = "series"  # series | list | pov | curiosity
    music_mood: str = "tech"  # se IGNORA en compose (no se mezcla música)
    subject_person: str = ""
    lang: str = "es"
    title: str
    thumbnail_text: str
    hashtags: list[str]
    segments: list[ScriptSegment]
    comment_bait: str  # pregunta corta (4-7 palabras) para overlay final

    def ordered_segments(self) -> list[tuple[str, "ScriptSegment"]]:
        return [(f"seg[{i}]", s) for i, s in enumerate(self.segments)]

    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments)


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float


class VoiceTrack(BaseModel):
    """Audio generado con timestamps por palabra."""

    lang: str
    audio_path: str
    duration_seconds: float
    words: list[WordTimestamp]


class VideoClip(BaseModel):
    """Un clip de B-roll descargado."""

    path: str
    duration_seconds: float
    width: int
    height: int
    keyword: str


class TimedSegment(BaseModel):
    """Un segmento del script con su ventana temporal en el voice track."""

    index: int  # 0 = hook, 1..N = body, N+1 = cta
    label: str  # "hook" | "body[0]" | ... | "cta"
    text: str
    start: float
    end: float
    visual_keywords: list[str]
    clips: list[VideoClip] = Field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start
