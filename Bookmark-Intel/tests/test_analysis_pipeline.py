from __future__ import annotations

import pytest

from analysis_pipeline import (
    AnalysisStage,
    concrete_resource_stage_names,
    run_concrete_resource_pipeline,
)


EXPECTED_STAGE_ORDER = (
    "source_capture",
    "universal_capture",
    "resource_coverage",
    "comic_resource",
    "video_resource",
    "video_precision",
    "youtube_description",
    "link_semantics",
)


def test_concrete_resource_stage_order_is_explicit() -> None:
    assert concrete_resource_stage_names() == EXPECTED_STAGE_ORDER


def test_pipeline_threads_each_stage_result_in_order() -> None:
    def stage(name: str) -> AnalysisStage:
        def runner(data, acquired, provider):
            return {**data, "trail": [*(data.get("trail") or []), name]}

        return AnalysisStage(name, runner)

    stages = (stage("one"), stage("two"), stage("three"))
    result = run_concrete_resource_pipeline({}, object(), None, stages=stages)
    assert result["trail"] == ["one", "two", "three"]


def test_pipeline_rejects_non_mapping_stage_result() -> None:
    broken = AnalysisStage("broken", lambda data, acquired, provider: None)

    with pytest.raises(TypeError, match="broken"):
        run_concrete_resource_pipeline({}, object(), None, stages=(broken,))
