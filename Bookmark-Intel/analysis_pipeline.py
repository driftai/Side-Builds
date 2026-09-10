from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from comic_resource import finalize_comic_resource
from link_semantics import normalize_link_semantics
from resource_coverage import finalize_resource_coverage
from source_capture import finalize_analysis
from universal_capture import universal_finalize
from video_precision import finalize_video_precision
from video_resource import finalize_video_resource
from youtube_description import finalize_youtube_description

AnalysisData = dict[str, Any]
StageRunner = Callable[[AnalysisData, Any, Any], AnalysisData]


@dataclass(frozen=True, slots=True)
class AnalysisStage:
    """One ordered transformation in the concrete-resource analysis pipeline."""

    name: str
    runner: StageRunner

    def apply(self, data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
        updated = self.runner(data, acquired, provider)
        if not isinstance(updated, dict):
            raise TypeError(f"Analysis stage {self.name!r} returned {type(updated).__name__}, expected dict")
        return updated


def _source_capture(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return finalize_analysis(data, acquired, provider)


def _universal_capture(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return universal_finalize(data, acquired)


def _resource_coverage(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return finalize_resource_coverage(data, acquired, provider)


def _comic_resource(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return finalize_comic_resource(data, acquired)


def _video_resource(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return finalize_video_resource(data, acquired)


def _video_precision(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return finalize_video_precision(data, acquired)


def _youtube_description(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return finalize_youtube_description(data, acquired)


def _link_semantics(data: AnalysisData, acquired: Any, provider: Any) -> AnalysisData:
    return normalize_link_semantics(data)


# Order is behavior. Later stages may intentionally refine fields produced by earlier stages,
# so new resource-specific passes belong here rather than as another ad-hoc call in intel.py.
CONCRETE_RESOURCE_STAGES: tuple[AnalysisStage, ...] = (
    AnalysisStage("source_capture", _source_capture),
    AnalysisStage("universal_capture", _universal_capture),
    AnalysisStage("resource_coverage", _resource_coverage),
    AnalysisStage("comic_resource", _comic_resource),
    AnalysisStage("video_resource", _video_resource),
    AnalysisStage("video_precision", _video_precision),
    AnalysisStage("youtube_description", _youtube_description),
    AnalysisStage("link_semantics", _link_semantics),
)


def concrete_resource_stage_names() -> tuple[str, ...]:
    return tuple(stage.name for stage in CONCRETE_RESOURCE_STAGES)


def run_concrete_resource_pipeline(
    data: AnalysisData,
    acquired: Any,
    provider: Any,
    *,
    stages: Iterable[AnalysisStage] | None = None,
) -> AnalysisData:
    """Run the ordered concrete-resource refinement pipeline.

    Keeping orchestration here makes precedence explicit and gives future passes one place to
    register, test, reorder, or condition stages without growing intel.py into a call chain.
    """

    current = data
    selected_stages = CONCRETE_RESOURCE_STAGES if stages is None else tuple(stages)
    for stage in selected_stages:
        current = stage.apply(current, acquired, provider)
    return current
