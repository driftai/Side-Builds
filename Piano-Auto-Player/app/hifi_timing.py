from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RelativeTimingConfig:
    """Keep local rhythm stable while allowing slow model/audio timing correction."""

    phrase_reset_ms: float = 180.0
    change_ratio: float = 0.06
    minimum_change_ms: float = 0.75
    maximum_change_ms: float = 3.0
    sparse_change_ratio: float = 0.025
    sparse_minimum_change_ms: float = 0.35
    sparse_maximum_change_ms: float = 1.25
    texture_flicker_max_clusters: int = 1
    texture_flicker_edge_gap_ms: float = 120.0


def stabilize_cluster_shifts(
    anchors: list[float], raw_shifts: list[float], config: RelativeTimingConfig | None = None,
    independent: list[bool] | None = None,
) -> tuple[list[float], dict[str, float | int]]:
    """Slew-limit adjacent attack corrections so they cannot create timing jumps.

    Absolute onset correction is useful, but independently correcting neighboring
    attacks can distort their inter-onset interval. A +18 ms correction followed
    immediately by 0 ms makes the second attack arrive 18 ms *earlier relative to
    the first*. That is heard as rushing/jumping even though each detector was
    locally plausible. Dense passages therefore change correction gradually;
    a real phrase gap may reset to the newly measured timing immediately.
    """
    if len(anchors) != len(raw_shifts):
        raise ValueError("anchors and raw_shifts must have the same length")
    if independent is not None and len(independent) != len(raw_shifts):
        raise ValueError("independent and raw_shifts must have the same length")
    if not raw_shifts:
        return [], _empty_stats()

    cfg = config or RelativeTimingConfig()
    locks = list(independent or [False] * len(raw_shifts))
    locks, texture_flicker_suppressed = _debounce_texture_flags(anchors, locks, cfg)
    stable = [float(raw_shifts[0])]
    limited = phrase_resets = sparse_resets = sparse_limited = 0
    max_raw_jump = max_stable_jump = max_guarded = 0.0

    for index in range(1, len(raw_shifts)):
        raw = float(raw_shifts[index])
        previous = stable[-1]
        gap = max(0.0, float(anchors[index]) - float(anchors[index - 1]))
        raw_jump = raw - previous
        max_raw_jump = max(max_raw_jump, abs(raw_jump))

        sparse_now = locks[index]
        sparse_before = locks[index - 1]
        if sparse_now != sparse_before:
            # Entering/leaving an exposed texture may adopt its own timing
            # estimate immediately, but consecutive sparse attacks must not
            # reset independently. v0.6.17 treated every sparse cluster as an
            # island, which could make an arpeggio jump between nearby timing
            # offsets even though each individual correction looked plausible.
            chosen = raw
            sparse_resets += int(abs(raw_jump) > 0.001)
        elif gap >= cfg.phrase_reset_ms:
            chosen = raw
            phrase_resets += int(abs(raw_jump) > 0.001)
        else:
            if sparse_now:
                allowance = max(
                    cfg.sparse_minimum_change_ms,
                    min(cfg.sparse_maximum_change_ms, gap * cfg.sparse_change_ratio),
                )
            else:
                allowance = max(
                    cfg.minimum_change_ms,
                    min(cfg.maximum_change_ms, gap * cfg.change_ratio),
                )
            chosen = max(previous - allowance, min(previous + allowance, raw))
            if abs(chosen - raw) > 0.001:
                limited += 1
                sparse_limited += int(sparse_now)
                max_guarded = max(max_guarded, abs(raw - chosen))

        max_stable_jump = max(max_stable_jump, abs(chosen - previous))
        stable.append(round(chosen, 3))

    return stable, {
        "hifi_timing_relative_slew_limited": limited,
        "hifi_timing_phrase_resets": phrase_resets,
        "hifi_timing_sparse_resets": sparse_resets,
        "hifi_timing_sparse_slew_limited": sparse_limited,
        "hifi_timing_texture_flicker_suppressed": texture_flicker_suppressed,
        "hifi_timing_raw_max_step_ms": round(max_raw_jump, 3),
        "hifi_timing_stable_max_step_ms": round(max_stable_jump, 3),
        "hifi_timing_max_step_guarded_ms": round(max_guarded, 3),
    }


def _debounce_texture_flags(
    anchors: list[float], flags: list[bool], cfg: RelativeTimingConfig,
) -> tuple[list[bool], int]:
    """Suppress a one-cluster sparse/dense classification flicker.

    A repeated arpeggio can briefly exceed the local density threshold for one
    attack (for example, a small chord inside an otherwise exposed pattern).
    Treating that single cluster as a real texture boundary creates two timing
    resets: sparse->dense and immediately dense->sparse. The notes are correct,
    but the reset pair is audible as a tiny jump. Only a short run surrounded by
    the same texture is folded back; persistent transitions and phrase gaps stay
    authoritative.
    """
    if len(flags) < 3 or len(flags) != len(anchors):
        return list(flags), 0
    result = list(flags)
    suppressed = 0
    index = 1
    max_run = max(0, int(cfg.texture_flicker_max_clusters))
    while index < len(flags) - 1:
        start = index
        value = flags[index]
        while index + 1 < len(flags) and flags[index + 1] == value:
            index += 1
        end = index
        run_length = end - start + 1
        left = start - 1
        right = end + 1
        if (
            run_length <= max_run
            and right < len(flags)
            and flags[left] == flags[right]
            and flags[left] != value
            and anchors[start] - anchors[left] < cfg.phrase_reset_ms
            and anchors[right] - anchors[end] < cfg.phrase_reset_ms
            and anchors[start] - anchors[left] <= cfg.texture_flicker_edge_gap_ms
            and anchors[right] - anchors[end] <= cfg.texture_flicker_edge_gap_ms
        ):
            for pos in range(start, end + 1):
                result[pos] = flags[left]
            suppressed += run_length
        index += 1
    return result, suppressed


def _empty_stats() -> dict[str, float | int]:
    return {
        "hifi_timing_relative_slew_limited": 0,
        "hifi_timing_phrase_resets": 0,
        "hifi_timing_sparse_resets": 0,
        "hifi_timing_sparse_slew_limited": 0,
        "hifi_timing_texture_flicker_suppressed": 0,
        "hifi_timing_raw_max_step_ms": 0.0,
        "hifi_timing_stable_max_step_ms": 0.0,
        "hifi_timing_max_step_guarded_ms": 0.0,
    }
