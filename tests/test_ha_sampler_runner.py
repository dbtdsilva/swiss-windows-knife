import threading
import time

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.sampler_runner import SamplerRunner


def test_submit_runs_fn_off_calling_thread_and_calls_on_done():
    runner = SamplerRunner()
    calling_thread = threading.get_ident()
    fn_thread = []
    done_thread = []
    done_value = []
    event = threading.Event()

    def fn():
        fn_thread.append(threading.get_ident())
        return "result"

    def on_done(value):
        done_thread.append(threading.get_ident())
        done_value.append(value)
        event.set()

    runner.submit(fn, on_done)
    assert event.wait(2.0), "on_done was not called within 2s"
    assert fn_thread[0] != calling_thread
    assert done_thread[0] != calling_thread
    assert done_value == ["result"]


def test_submit_swallows_exceptions_and_skips_on_done():
    runner = SamplerRunner()
    on_done_calls = []
    after_event = threading.Event()

    def fn_raises():
        raise RuntimeError("boom")

    def follow_up():
        after_event.set()

    runner.submit(fn_raises, lambda v: on_done_calls.append(v))
    runner.submit(follow_up, lambda v: None)
    assert after_event.wait(2.0)
    assert on_done_calls == []


def test_runs_submissions_in_order():
    runner = SamplerRunner()
    seen = []
    last = threading.Event()

    def make_fn(n):
        def fn():
            seen.append(n)
            time.sleep(0.01)
            return n
        return fn

    def on_done_n(n):
        if n == 4:
            last.set()

    for i in range(5):
        runner.submit(make_fn(i), on_done_n)
    assert last.wait(2.0)
    assert seen == [0, 1, 2, 3, 4]
