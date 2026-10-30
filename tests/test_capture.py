from gestia.capture import CameraError, CaptureProducer, CapturedFrame, LatestFrameBuffer


class FailingCamera:
    def __init__(self) -> None:
        self.closed = False

    def open(self) -> None:
        pass

    def read(self) -> tuple[bool, object]:
        return False, None

    def close(self) -> None:
        self.closed = True


class UnavailableCamera(FailingCamera):
    def open(self) -> None:
        raise CameraError("cámara simulada no disponible")


def test_latest_frame_buffer_replaces_unprocessed_frame() -> None:
    buffer = LatestFrameBuffer()
    first = CapturedFrame(1, 10, object())
    second = CapturedFrame(2, 20, object())
    buffer.put(first)
    buffer.put(second)
    assert buffer.replaced == 1
    assert buffer.take() is second


def test_camera_open_failure_is_understandable() -> None:
    producer = CaptureProducer(UnavailableCamera(), LatestFrameBuffer())
    try:
        producer.start()
    except CameraError as exc:
        assert "simulada" in str(exc)
    else:
        raise AssertionError("Se esperaba CameraError")


def test_repeated_read_failure_releases_camera() -> None:
    camera = FailingCamera()
    producer = CaptureProducer(camera, LatestFrameBuffer())
    producer.start()
    assert producer._thread is not None
    producer._thread.join(timeout=1.0)
    assert isinstance(producer.error, CameraError)
    assert camera.closed
