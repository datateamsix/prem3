"""MTA domain lifecycle. Envelope MeasurementTrackStatus remains separate."""

from __future__ import annotations

from enum import StrEnum


class MTATrackStage(StrEnum):
    AVAILABLE_TO_CONFIGURE = "AVAILABLE_TO_CONFIGURE"
    SOURCE_DISCOVERED = "SOURCE_DISCOVERED"
    CONFIGURING = "CONFIGURING"
    PROVISIONING = "PROVISIONING"
    ASSESSING_INPUT = "ASSESSING_INPUT"
    MTA_INPUT_READY = "MTA_INPUT_READY"
    RUN_QUEUED = "RUN_QUEUED"
    RUNNING = "RUNNING"
    RESULTS_READY = "RESULTS_READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


# M5-00 does not advance past MTA_INPUT_READY via live execution.
M5_00_TERMINAL_STAGES = frozenset(
    {
        MTATrackStage.AVAILABLE_TO_CONFIGURE,
        MTATrackStage.SOURCE_DISCOVERED,
        MTATrackStage.CONFIGURING,
        MTATrackStage.PROVISIONING,
        MTATrackStage.ASSESSING_INPUT,
        MTATrackStage.MTA_INPUT_READY,
        MTATrackStage.FAILED,
    }
)
