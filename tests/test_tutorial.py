"""Tutorial y modo de práctica (P3-26)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gestia.gestures import DEFAULT_ACTIONS, Action, GestureEvent, GestureId  # noqa: E402
from gestia.profiles import Profile, ProfileStore  # noqa: E402
from gestia.tutorial import (  # noqa: E402
    EXIT_TARGET,
    GESTURE_TARGET,
    MOVE_TARGETS,
    REACH_MS,
    LessonKind,
    TutorialSession,
    build_lessons,
    practice_lessons,
)
from gestia.ui_tutorial import TutorialDialog  # noqa: E402

CENTER = (GESTURE_TARGET.x, GESTURE_TARGET.y)
CORNER = (0.02, 0.98)


def calibrated_profile() -> Profile:
    return Profile("p", "P")


def lessons_for(profile: Profile, calibrated=lambda _g: True):
    return build_lessons(profile.gestures, profile.actions, calibrated)


def event(gesture: GestureId, at: int = 0) -> GestureEvent:
    return GestureEvent(gesture, DEFAULT_ACTIONS[gesture], at)


def test_lessons_follow_the_profile_mapping() -> None:
    lessons = lessons_for(calibrated_profile())
    assert lessons[0].kind is LessonKind.MOVE
    assert lessons[-1].kind is LessonKind.DONE
    taught = [lesson.action for lesson in lessons if lesson.kind is LessonKind.GESTURE]
    assert taught[0] is Action.LEFT_CLICK
    assert taught[-1] is Action.PAUSE
    assert set(taught) == set(DEFAULT_ACTIONS.values())


def test_disabled_or_uncalibrated_gestures_are_not_taught() -> None:
    profile = calibrated_profile()
    profile.gestures[GestureId.SMILE].enabled = False
    lessons = lessons_for(profile, calibrated=lambda g: g is not GestureId.PUCKER)
    taught = {lesson.gesture for lesson in lessons}
    assert GestureId.SMILE not in taught and GestureId.PUCKER not in taught
    assert GestureId.WINK_LEFT in taught


def test_move_lesson_needs_each_target_held() -> None:
    session = TutorialSession(lessons_for(calibrated_profile()), advance_ms=100)
    now = 0
    for target in MOVE_TARGETS:
        point = (target.x, target.y)
        assert not session.feed(point, [], now).success
        update = session.feed(point, [], now + REACH_MS)
        assert update.success and target.id in update.done
        now += REACH_MS + 10
    assert "Muy bien" in update.message
    session.feed(CENTER, [], now + 100)
    assert session.lesson.kind is LessonKind.GESTURE


def test_click_lesson_requires_pointer_on_target() -> None:
    lessons = lessons_for(calibrated_profile())
    session = TutorialSession(lessons, advance_ms=100)
    session.skip()
    assert session.lesson.gesture is GestureId.WINK_LEFT
    update = session.feed(CORNER, [event(GestureId.WINK_LEFT)], 0)
    assert not update.success and "círculo" in update.message
    update = session.feed(CENTER, [event(GestureId.WINK_RIGHT)], 10)
    assert not update.success and "Guiño izquierdo" in update.message
    update = session.feed(CENTER, [event(GestureId.WINK_LEFT)], 20)
    assert update.success and "Perfecto" in update.message
    session.feed(CENTER, [], 200)
    assert session.lesson.gesture is GestureId.WINK_RIGHT


def test_non_click_lesson_works_anywhere_and_tutorial_finishes() -> None:
    lessons = lessons_for(calibrated_profile())
    session = TutorialSession(lessons, advance_ms=0)
    pause_index = next(i for i, item in enumerate(lessons) if item.action is Action.PAUSE)
    session.go_to(pause_index)
    assert session.feed(CORNER, [event(GestureId.BLINK)], 0).success
    update = session.feed(CORNER, [], 1)
    assert update.lesson.kind is LessonKind.DONE and update.finished


def test_lost_face_shows_message_and_recovers() -> None:
    session = TutorialSession(lessons_for(calibrated_profile()))
    assert "No vemos tu rostro" in session.feed(None, [], 0).message
    assert session.feed(CENTER, [], 1).message == session.lesson.instruction


def test_practice_reports_gestures_and_exits_with_click() -> None:
    session = TutorialSession(practice_lessons())
    update = session.feed(CORNER, [event(GestureId.PUCKER)], 0)
    assert "Modo desplazamiento" in update.message and not update.finished
    save = next(t for t in session.lesson.targets if t.id == "guardar")
    update = session.feed((save.x, save.y), [event(GestureId.WINK_LEFT)], 1)
    assert "guardar" in update.done and "Guardar" in update.message
    exit_target = next(t for t in session.lesson.targets if t.id == EXIT_TARGET)
    assert session.feed((exit_target.x, exit_target.y), [event(GestureId.WINK_RIGHT)], 2).finished


def test_restart_and_skip() -> None:
    session = TutorialSession(lessons_for(calibrated_profile()))
    session.skip()
    session.skip()
    assert session.index == 2
    session.restart()
    assert session.index == 0 and not session.done


def test_tutorial_flag_is_saved_and_old_profiles_load(tmp_path) -> None:
    store = ProfileStore(tmp_path)
    profile = store.load_active()
    assert not profile.tutorial_done
    profile.tutorial_done = True
    store.save(profile)
    assert ProfileStore(tmp_path).load_active().tutorial_done
    raw = Profile("viejo", "Viejo").to_dict()
    del raw["onboarding"]
    assert not Profile.from_dict(raw).tutorial_done
    raw["onboarding"] = {"tutorial_done": "sí"}
    with pytest.raises(ValueError):
        Profile.from_dict(raw)


def test_restore_defaults_keeps_tutorial_flag() -> None:
    profile = calibrated_profile()
    profile.tutorial_done = True
    profile.restore_defaults()
    assert profile.tutorial_done


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_dialog_plays_sound_and_closes_practice(qt_app) -> None:
    sounds = []
    dialog = TutorialDialog(TutorialSession(practice_lessons()), lambda: sounds.append(1))
    closed = []
    dialog.completed.connect(closed.append)
    exit_target = next(t for t in dialog.session.lesson.targets if t.id == EXIT_TARGET)
    dialog.feed((exit_target.x, exit_target.y), [event(GestureId.WINK_LEFT)], 5)
    assert sounds and dialog._closing
    dialog._finish()
    assert closed == [False]


def test_dialog_lists_lessons_and_skips(qt_app) -> None:
    dialog = TutorialDialog(TutorialSession(lessons_for(calibrated_profile())))
    assert dialog.lessons_list.count() == len(dialog.session.lessons)
    dialog.skip()
    assert dialog.session.index == 1
    assert dialog.title.text() == dialog.session.lesson.title
