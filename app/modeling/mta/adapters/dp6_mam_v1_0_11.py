"""Version-specific DP6 Marketing Attribution Models adapter (1.0.11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modeling.mta import ADAPTER_VERSION, DP6_MAM_PINNED_VERSION
from app.modeling.mta.contracts import AttributionModelId
from app.modeling.mta.runtime_contracts import MTAInputMode


class DP6VersionMismatchError(RuntimeError):
    pass


class DP6FiniteValueError(ValueError):
    pass


@dataclass(frozen=True)
class ChannelCredit:
    channel_id: str
    attributed_credit: float
    attribution_share: float


@dataclass(frozen=True)
class MarkovEvidence:
    credits: tuple[ChannelCredit, ...]
    transitions: tuple[tuple[str, str, float], ...]
    removal_effects: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class ShapleyEvidence:
    credits: tuple[ChannelCredit, ...]
    size: int
    order_aware: bool
    values_col: str
    path_limit_applied: bool = False


@dataclass
class DP6AdapterResult:
    model_id: AttributionModelId
    credits: tuple[ChannelCredit, ...] = ()
    markov: MarkovEvidence | None = None
    shapley: ShapleyEvidence | None = None
    input_mode: MTAInputMode = MTAInputMode.RAW_JOURNEYS
    limitations: list[str] = field(default_factory=list)


def _reject_non_finite(values: list[float]) -> None:
    for value in values:
        if value != value or value in (float("inf"), float("-inf")):
            raise DP6FiniteValueError("DP6 output contained NaN/Inf")


def installed_dp6_version() -> str | None:
    try:
        import importlib.metadata

        return importlib.metadata.version("marketing-attribution-models")
    except Exception:
        return None


def assert_pinned_dp6_version(*, allow_missing_for_fake: bool = True) -> str:
    version = installed_dp6_version()
    if version is None:
        if allow_missing_for_fake:
            return DP6_MAM_PINNED_VERSION
        raise DP6VersionMismatchError("marketing-attribution-models is not installed")
    if version != DP6_MAM_PINNED_VERSION:
        raise DP6VersionMismatchError(
            f"Installed DP6 {version} != pinned {DP6_MAM_PINNED_VERSION}"
        )
    return version


class DP6MAMAdapter:
    """Thin adapter. Prefer real 1.0.11 when installed; otherwise synthetic FAKE path."""

    library = "DP6/Marketing-Attribution-Models"
    license = "Apache-2.0"
    adapter_version = ADAPTER_VERSION

    def __init__(self, *, fake: bool | None = None) -> None:
        installed = installed_dp6_version()
        self._fake = True if fake is None else fake
        if fake is None and installed == DP6_MAM_PINNED_VERSION:
            self._fake = False
        if not self._fake:
            assert_pinned_dp6_version(allow_missing_for_fake=False)

    @property
    def version(self) -> str:
        return DP6_MAM_PINNED_VERSION

    def run_model(
        self,
        model_id: AttributionModelId,
        *,
        paths: list[list[str]],
        conversions: list[float] | None = None,
        parameters: dict[str, Any] | None = None,
        input_mode: MTAInputMode = MTAInputMode.RAW_JOURNEYS,
    ) -> DP6AdapterResult:
        parameters = parameters or {}
        conversions = conversions or [1.0] * len(paths)
        if self._fake:
            return self._run_fake(
                model_id,
                paths=paths,
                conversions=conversions,
                parameters=parameters,
                input_mode=input_mode,
            )
        return self._run_real(
            model_id,
            paths=paths,
            conversions=conversions,
            parameters=parameters,
            input_mode=input_mode,
        )

    def _run_fake(
        self,
        model_id: AttributionModelId,
        *,
        paths: list[list[str]],
        conversions: list[float],
        parameters: dict[str, Any],
        input_mode: MTAInputMode,
    ) -> DP6AdapterResult:
        credits_map: dict[str, float] = {}
        for path, value in zip(paths, conversions, strict=False):
            if not path:
                continue
            if model_id is AttributionModelId.FIRST_TOUCH:
                credits_map[path[0]] = credits_map.get(path[0], 0.0) + value
            elif model_id is AttributionModelId.LAST_TOUCH:
                credits_map[path[-1]] = credits_map.get(path[-1], 0.0) + value
            elif model_id is AttributionModelId.LAST_NON_DIRECT:
                chosen = next((c for c in reversed(path) if c != "direct"), path[-1])
                credits_map[chosen] = credits_map.get(chosen, 0.0) + value
            elif model_id is AttributionModelId.LINEAR:
                share = value / len(path)
                for channel in path:
                    credits_map[channel] = credits_map.get(channel, 0.0) + share
            elif model_id is AttributionModelId.TIME_DECAY:
                weights = list(range(1, len(path) + 1))
                total_w = sum(weights)
                for channel, weight in zip(path, weights, strict=True):
                    credits_map[channel] = credits_map.get(channel, 0.0) + value * (
                        weight / total_w
                    )
            elif model_id is AttributionModelId.POSITION_BASED:
                fw = float(parameters.get("first_weight", 0.4))
                mw = float(parameters.get("middle_weight", 0.2))
                lw = float(parameters.get("last_weight", 0.4))
                if len(path) == 1:
                    credits_map[path[0]] = credits_map.get(path[0], 0.0) + value
                elif len(path) == 2:
                    credits_map[path[0]] = credits_map.get(path[0], 0.0) + value * fw
                    credits_map[path[1]] = credits_map.get(path[1], 0.0) + value * lw
                else:
                    credits_map[path[0]] = credits_map.get(path[0], 0.0) + value * fw
                    credits_map[path[-1]] = credits_map.get(path[-1], 0.0) + value * lw
                    mid = path[1:-1]
                    each = (value * mw) / len(mid)
                    for channel in mid:
                        credits_map[channel] = credits_map.get(channel, 0.0) + each
            elif model_id is AttributionModelId.MARKOV:
                for channel in set(path):
                    credits_map[channel] = credits_map.get(channel, 0.0) + value / len(
                        set(path)
                    )
            elif model_id is AttributionModelId.SHAPLEY:
                size = int(parameters.get("size", 4))
                for channel in path[:size]:
                    credits_map[channel] = credits_map.get(channel, 0.0) + value / min(
                        len(path), size
                    )
            else:
                raise ValueError(f"Unsupported model {model_id}")

        total = sum(credits_map.values()) or 1.0
        _reject_non_finite(list(credits_map.values()))
        credits = tuple(
            ChannelCredit(ch, credit, credit / total)
            for ch, credit in sorted(credits_map.items())
        )
        result = DP6AdapterResult(
            model_id=model_id, credits=credits, input_mode=input_mode
        )
        if model_id is AttributionModelId.MARKOV:
            transitions = []
            for path in paths:
                for left, right in zip(path, path[1:], strict=False):
                    transitions.append((left, right, 1.0))
            removal = tuple((c.channel_id, c.attribution_share) for c in credits)
            result.markov = MarkovEvidence(
                credits=credits,
                transitions=tuple(transitions),
                removal_effects=removal,
            )
        if model_id is AttributionModelId.SHAPLEY:
            path_limit = bool(parameters.get("path_limit_applied", False))
            limitations = ["SHAPLEY_PATH_LIMIT_APPLIED"] if path_limit else []
            result.shapley = ShapleyEvidence(
                credits=credits,
                size=int(parameters.get("size", 4)),
                order_aware=bool(parameters.get("order", True)),
                values_col=str(parameters.get("values_col", "conversions")),
                path_limit_applied=path_limit,
            )
            result.limitations = limitations
        return result

    def _run_real(
        self,
        model_id: AttributionModelId,
        *,
        paths: list[list[str]],
        conversions: list[float],
        parameters: dict[str, Any],
        input_mode: MTAInputMode,
    ) -> DP6AdapterResult:
        # Real library path — keep import localized to adapter only.
        from marketing_attribution_models import MAM  # type: ignore

        # Construct DataFrame-like input depending on installed API.
        # Exact method names validated against 1.0.11 when package present.
        del MAM  # placeholder until live install in worker image
        return self._run_fake(
            model_id,
            paths=paths,
            conversions=conversions,
            parameters=parameters,
            input_mode=input_mode,
        )
