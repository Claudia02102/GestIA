import pytest

from gestia import features as f
from gestia.features import extract_features


def synthetic_face(mouth_gap: float = 0.01, eye_gap: float = 0.03, nose_x: float = 0.5):
    points = [(0.5, 0.5, 0.0)] * 478
    points = list(points)

    def put(index: int, x: float, y: float) -> None:
        points[index] = (x, y, 0.0)

    put(f.CHEEK_RIGHT, 0.3, 0.5)
    put(f.CHEEK_LEFT, 0.7, 0.5)
    put(f.FOREHEAD, 0.5, 0.2)
    put(f.CHIN, 0.5, 0.8)
    put(f.NOSE_TIP, nose_x, 0.5)
    for eye, x0 in ((f.EYE_RIGHT, 0.35), (f.EYE_LEFT, 0.55)):
        p1, p2, p3, p4, p5, p6 = eye
        put(p1, x0, 0.4)
        put(p4, x0 + 0.1, 0.4)
        put(p2, x0 + 0.03, 0.4 - eye_gap / 2)
        put(p3, x0 + 0.07, 0.4 - eye_gap / 2)
        put(p6, x0 + 0.03, 0.4 + eye_gap / 2)
        put(p5, x0 + 0.07, 0.4 + eye_gap / 2)
    put(f.LIP_UPPER_INNER, 0.5, 0.65 - mouth_gap / 2)
    put(f.LIP_LOWER_INNER, 0.5, 0.65 + mouth_gap / 2)
    put(f.MOUTH_INNER_RIGHT, 0.45, 0.65)
    put(f.MOUTH_INNER_LEFT, 0.55, 0.65)
    put(f.MOUTH_CORNER_RIGHT, 0.44, 0.65)
    put(f.MOUTH_CORNER_LEFT, 0.56, 0.65)
    put(f.BROW_RIGHT, 0.4, 0.33)
    put(f.BROW_LEFT, 0.6, 0.33)
    return points


def test_ratios_on_synthetic_face() -> None:
    features = extract_features(synthetic_face(), aspect=1.0)
    assert features is not None
    assert features.yaw == pytest.approx(0.5)
    assert features.pitch == pytest.approx(0.5)
    assert features.eye_left == pytest.approx(0.3)
    assert features.eye_right == pytest.approx(0.3)
    assert features.mouth_open == pytest.approx(0.1)
    assert features.smile == pytest.approx(0.3)


def test_gestures_move_the_expected_metric() -> None:
    neutral = extract_features(synthetic_face(), 1.0)
    open_mouth = extract_features(synthetic_face(mouth_gap=0.05), 1.0)
    closed_eyes = extract_features(synthetic_face(eye_gap=0.005), 1.0)
    turned = extract_features(synthetic_face(nose_x=0.6), 1.0)
    assert open_mouth.mouth_open > neutral.mouth_open * 4
    assert closed_eyes.eye_left < neutral.eye_left / 4
    assert turned.yaw == pytest.approx(0.75)


def test_ratios_do_not_depend_on_frame_aspect_for_square_pixels() -> None:
    wide = extract_features(synthetic_face(), aspect=16 / 9)
    assert wide.yaw == pytest.approx(0.5)


def test_incomplete_landmarks_return_none() -> None:
    assert extract_features([(0.0, 0.0, 0.0)] * 10, 1.0) is None
    assert extract_features(synthetic_face(), 0.0) is None
