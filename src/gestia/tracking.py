from dataclasses import dataclass

from gestia.domain import TrackingState


@dataclass(slots=True)
class TrackingStateMachine:
    stable_detection_ms: int = 300
    state: TrackingState = TrackingState.STOPPED
    _detection_started_ms: int | None = None

    def start(self) -> TrackingState:
        self._detection_started_ms = None
        self.state = TrackingState.SEARCHING
        return self.state

    def stop(self) -> TrackingState:
        self._detection_started_ms = None
        self.state = TrackingState.STOPPED
        return self.state

    def fail(self) -> TrackingState:
        self._detection_started_ms = None
        self.state = TrackingState.ERROR
        return self.state

    def observe(self, detected: bool, timestamp_ms: int) -> TrackingState:
        if self.state in (TrackingState.STOPPED, TrackingState.ERROR):
            return self.state
        if not detected:
            self._detection_started_ms = None
            if self.state is TrackingState.TRACKING:
                self.state = TrackingState.LOST
            return self.state
        if self.state is TrackingState.TRACKING:
            return self.state
        if self._detection_started_ms is None:
            self._detection_started_ms = timestamp_ms
        if timestamp_ms - self._detection_started_ms >= self.stable_detection_ms:
            self.state = TrackingState.TRACKING
        return self.state


@dataclass(slots=True)
class ResultFreshnessGate:
    max_age_ms: int
    last_timestamp_ms: int = -1

    def accept(self, result_timestamp_ms: int, now_ms: int) -> bool:
        if result_timestamp_ms <= self.last_timestamp_ms:
            return False
        if now_ms - result_timestamp_ms > self.max_age_ms:
            return False
        self.last_timestamp_ms = result_timestamp_ms
        return True
