"""Version-specific DP6 Marketing Attribution Models adapter (1.0.11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.domain.channels import cached_channel_registry
from app.modeling.mta import ADAPTER_VERSION, DP6_MAM_PINNED_VERSION
from app.modeling.mta.contracts import AttributionModelId
from app.modeling.mta.runtime_contracts import MTAFailureClass, MTAInputMode

try:
    from marketing_attribution_models import MAM
except ImportError:  # pragma: no cover - API image does not install the dp6 extra
    MAM = None

SHARE_SUM_TOLERANCE = 1e-6
DP6_SPECIAL_STATES = frozenset({"(inicio)", "(conversion)", "(null)"})
LAST_NON_DIRECT_CHANNEL = "direct"


class DP6VersionMismatchError(RuntimeError):
    pass


class DP6FiniteValueError(ValueError):
    pass


class DP6UnknownChannelError(ValueError):
    failure_class = MTAFailureClass.MTA_RUNTIME_INVALID_OUTPUT


class DP6AccountingError(ValueError):
    failure_class = MTAFailureClass.MTA_RUNTIME_INVALID_OUTPUT


class MTAFakeRuntimeNotAllowed(RuntimeError):
    failure_class = MTAFailureClass.MTA_FAKE_RUNTIME_NOT_ALLOWED


class DP6MissingParameterError(ValueError):
    failure_class = MTAFailureClass.MTA_RUNTIME_INPUT_ERROR


class DP6ApiError(RuntimeError):
    failure_class = MTAFailureClass.MTA_RUNTIME_DP6_API_ERROR


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
    runtime: str = "TEST_FAKE_RUNTIME"
    warnings: list[str] = field(default_factory=list)


@dataclass
class DP6ResultBundle:
    heuristic_channel_results: tuple[ChannelCredit, ...] = ()
    markov_channel_results: tuple[ChannelCredit, ...] = ()
    markov_transition_rows: tuple[tuple[str, str, float], ...] = ()
    markov_removal_effects: tuple[tuple[str, float], ...] = ()
    shapley_channel_results: tuple[ChannelCredit, ...] = ()
    model_execution_evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    runtime_metadata: dict[str, Any] = field(default_factory=dict)


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


def assert_real_runtime_allowed(*, runtime_mode: str, proof_label: str, fake: bool) -> None:
    if fake and (
        runtime_mode in {"LIVE", "SYNTHETIC_DEMO"} or proof_label in {"LIVE", "SYNTHETIC_DEMO"}
    ):
        raise MTAFakeRuntimeNotAllowed(
            "LIVE / SYNTHETIC_DEMO execution cannot use the fake DP6 adapter."
        )


def _require_param(parameters: dict[str, Any], name: str) -> Any:
    if name not in parameters:
        raise DP6MissingParameterError(f"Missing required model parameter '{name}'")
    return parameters[name]


def _credits_from_map(credits_map: dict[str, float]) -> tuple[ChannelCredit, ...]:
    _reject_non_finite(list(credits_map.values()))
    total = sum(credits_map.values())
    if total <= 0:
        raise DP6AccountingError("DP6 credits summed to zero")
    credits = tuple(
        ChannelCredit(ch, credit, credit / total)
        for ch, credit in sorted(credits_map.items())
    )
    share_sum = sum(c.attribution_share for c in credits)
    if abs(share_sum - 1.0) > SHARE_SUM_TOLERANCE:
        raise DP6AccountingError(
            f"attribution_share sum {share_sum} outside tolerance {SHARE_SUM_TOLERANCE}"
        )
    return credits


def _assert_canonical_channels(credits: tuple[ChannelCredit, ...]) -> None:
    registry = cached_channel_registry(1)
    known = set(registry.channel_ids())
    unknown = [c.channel_id for c in credits if c.channel_id not in known]
    if unknown:
        raise DP6UnknownChannelError(
            f"DP6 returned unknown marketing channel IDs: {sorted(unknown)}"
        )


def _frame_credits(frame: pd.DataFrame | pd.Series) -> tuple[ChannelCredit, ...]:
    if isinstance(frame, pd.Series):
        frame = frame.reset_index()
        frame.columns = ["channels", "value"]
    if not isinstance(frame, pd.DataFrame):
        raise DP6AccountingError("DP6 grouped frame was not a DataFrame")
    value_col = [c for c in frame.columns if c != "channels"][-1]
    credits_map: dict[str, float] = {}
    for _, row in frame.iterrows():
        channel = str(row["channels"])
        if channel in DP6_SPECIAL_STATES:
            continue
        credits_map[channel] = credits_map.get(channel, 0.0) + float(row[value_col])
    credits = _credits_from_map(credits_map)
    _assert_canonical_channels(credits)
    return credits


class DP6MAMAdapter:
    """Thin adapter. Real 1.0.11 for production; explicit fake=True for unit tests."""

    library = "DP6/Marketing-Attribution-Models"
    license = "Apache-2.0"
    adapter_version = ADAPTER_VERSION

    def __init__(self, *, fake: bool | None = None) -> None:
        installed = installed_dp6_version()
        if fake is True:
            self._fake = True
        elif fake is False:
            self._fake = False
            assert_pinned_dp6_version(allow_missing_for_fake=False)
        else:
            self._fake = installed != DP6_MAM_PINNED_VERSION
            if not self._fake:
                assert_pinned_dp6_version(allow_missing_for_fake=False)

    @property
    def is_fake(self) -> bool:
        return self._fake

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

        credits = _credits_from_map(credits_map)
        result = DP6AdapterResult(
            model_id=model_id,
            credits=credits,
            input_mode=input_mode,
            runtime="TEST_FAKE_RUNTIME",
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

    def _journeys_frame(
        self,
        *,
        paths: list[list[str]],
        conversions: list[float],
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for index, (path, value) in enumerate(zip(paths, conversions, strict=False)):
            if not path:
                continue
            rows.append(
                {
                    "journey_id": f"j{index}",
                    "channels": list(path),
                    "converted": True,
                    "conversion_value": float(value),
                }
            )
        if not rows:
            raise DP6MissingParameterError("No journeys supplied to DP6")
        return pd.DataFrame(rows)

    def _mam(self, frame: pd.DataFrame) -> Any:
        if MAM is None:
            raise DP6VersionMismatchError("marketing-attribution-models is not installed")
        return MAM(
            frame,
            group_channels=False,
            channels_colname="channels",
            journey_with_conv_colname="converted",
            conversion_value="conversion_value",
            group_channels_by_id_list=["journey_id"],
            path_separator=" > ",
            verbose=False,
        )

    def _run_real(
        self,
        model_id: AttributionModelId,
        *,
        paths: list[list[str]],
        conversions: list[float],
        parameters: dict[str, Any],
        input_mode: MTAInputMode,
    ) -> DP6AdapterResult:
        assert_pinned_dp6_version(allow_missing_for_fake=False)
        mam = self._mam(self._journeys_frame(paths=paths, conversions=conversions))
        try:
            if model_id is AttributionModelId.FIRST_TOUCH:
                _values, frame = mam.attribution_first_click()
                credits = _frame_credits(frame)
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=credits,
                    input_mode=input_mode,
                    runtime="DP6_1_0_11",
                )
            if model_id is AttributionModelId.LAST_TOUCH:
                _values, frame = mam.attribution_last_click()
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=_frame_credits(frame),
                    input_mode=input_mode,
                    runtime="DP6_1_0_11",
                )
            if model_id is AttributionModelId.LAST_NON_DIRECT:
                _values, frame = mam.attribution_last_click_non(
                    but_not_this_channel=LAST_NON_DIRECT_CHANNEL
                )
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=_frame_credits(frame),
                    input_mode=input_mode,
                    runtime="DP6_1_0_11",
                )
            if model_id is AttributionModelId.LINEAR:
                _values, frame = mam.attribution_linear()
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=_frame_credits(frame),
                    input_mode=input_mode,
                    runtime="DP6_1_0_11",
                )
            if model_id is AttributionModelId.TIME_DECAY:
                decay = float(_require_param(parameters, "decay_over_time"))
                frequency = float(_require_param(parameters, "frequency"))
                _values, frame = mam.attribution_time_decay(
                    decay_over_time=decay, frequency=frequency
                )
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=_frame_credits(frame),
                    input_mode=input_mode,
                    runtime="DP6_1_0_11",
                )
            if model_id is AttributionModelId.POSITION_BASED:
                first = float(_require_param(parameters, "first_weight"))
                middle = float(_require_param(parameters, "middle_weight"))
                last = float(_require_param(parameters, "last_weight"))
                if abs((first + middle + last) - 1.0) > 1e-9:
                    raise DP6MissingParameterError(
                        "POSITION_BASED weights must sum to 1.0; invalid values are not normalized"
                    )
                _values, frame = mam.attribution_position_based(
                    list_positions_first_middle_last=[first, middle, last]
                )
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=_frame_credits(frame),
                    input_mode=input_mode,
                    runtime="DP6_1_0_11",
                )
            if model_id is AttributionModelId.MARKOV:
                same_state = bool(_require_param(parameters, "transition_to_same_state"))
                as_freq = bool(_require_param(parameters, "conversion_value_as_frequency"))
                _values, frame, matrix, removal = mam.attribution_markov(
                    transition_to_same_state=same_state,
                    conversion_value_as_frequency=as_freq,
                )
                credits = _frame_credits(frame)
                transitions: list[tuple[str, str, float]] = []
                for orig in matrix.index:
                    for dest in matrix.columns:
                        prob = float(matrix.loc[orig, dest])
                        if prob:
                            transitions.append((str(orig), str(dest), prob))
                effects = tuple(
                    (str(idx), float(row["removal_effect"]))
                    for idx, row in removal.iterrows()
                    if str(idx) not in DP6_SPECIAL_STATES
                )
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=credits,
                    markov=MarkovEvidence(
                        credits=credits,
                        transitions=tuple(transitions),
                        removal_effects=effects,
                    ),
                    input_mode=input_mode,
                    runtime="DP6_1_0_11",
                )
            if model_id is AttributionModelId.SHAPLEY:
                size = int(_require_param(parameters, "size"))
                order = bool(_require_param(parameters, "order"))
                values_col = str(_require_param(parameters, "values_col"))
                path_limit = any(len(set(path)) > size for path in paths if path)
                _table, frame = mam.attribution_shapley(
                    size=size, order=order, values_col=values_col
                )
                credits = _frame_credits(frame)
                limitations = ["SHAPLEY_PATH_LIMIT_APPLIED"] if path_limit else []
                return DP6AdapterResult(
                    model_id=model_id,
                    credits=credits,
                    shapley=ShapleyEvidence(
                        credits=credits,
                        size=size,
                        order_aware=order,
                        values_col=values_col,
                        path_limit_applied=path_limit,
                    ),
                    input_mode=input_mode,
                    limitations=limitations,
                    runtime="DP6_1_0_11",
                )
        except (
            DP6FiniteValueError,
            DP6UnknownChannelError,
            DP6AccountingError,
            DP6MissingParameterError,
            DP6VersionMismatchError,
            MTAFakeRuntimeNotAllowed,
            DP6ApiError,
        ):
            raise
        except Exception as exc:
            raise DP6ApiError(f"DP6 1.0.11 invocation failed for {model_id}") from exc
        raise ValueError(f"Unsupported model {model_id}")
