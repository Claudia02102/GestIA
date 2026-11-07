from gestia.domain import TrackingState
from gestia.tracking import ResultFreshnessGate, TrackingStateMachine


def test_requires_stable_detection_before_tracking() -> None:
    machine = TrackingStateMachine(stable_detection_ms=300)
    assert machine.start() is TrackingState.SEARCHING
    assert machine.observe(True, 1_000) is TrackingState.SEARCHING
    assert machine.observe(True, 1_299) is TrackingState.SEARCHING
    assert machine.observe(True, 1_300) is TrackingState.TRACKING


def test_loss_invalidates_immediately_and_recovers_stably() -> None:
    machine = TrackingStateMachine(stable_detection_ms=200)
    machine.start()
    machine.observe(True, 100)
    assert machine.observe(True, 300) is TrackingState.TRACKING
    assert machine.observe(False, 301) is TrackingState.LOST
    assert machine.observe(True, 500) is TrackingState.LOST
    assert machine.observe(True, 700) is TrackingState.TRACKING


def test_search_without_face_does_not_invent_detection() -> None:
    machine = TrackingStateMachine()
    machine.start()
    assert machine.observe(False, 10_000) is TrackingState.SEARCHING


def test_error_is_distinct_and_restartable() -> None:
    machine = TrackingStateMachine()
    machine.start()
    assert machine.fail() is TrackingState.ERROR
    assert machine.observe(True, 1_000) is TrackingState.ERROR
    assert machine.start() is TrackingState.SEARCHING


def test_freshness_gate_rejects_old_and_out_of_order_results() -> None:
    gate = ResultFreshnessGate(max_age_ms=100)
    assert gate.accept(950, 1_000)
    assert not gate.accept(940, 1_001)
    assert not gate.accept(1_000, 1_101)
    assert gate.accept(1_050, 1_100)
