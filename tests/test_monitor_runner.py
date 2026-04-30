import threading

from swiss_windows_knife.base.monitor_runner import _MonitorRunner


def test_runner_processes_tasks_in_submission_order():
    runner = _MonitorRunner()

    results: list[int] = []
    done = threading.Event()

    def task(value: int) -> None:
        results.append(value)
        if value == 3:
            done.set()

    runner.submit(task, 1)
    runner.submit(task, 2)
    runner.submit(task, 3)

    assert done.wait(timeout=2.0), "runner did not drain in time"
    assert results == [1, 2, 3]


def test_runner_exception_does_not_kill_worker():
    runner = _MonitorRunner()

    results: list[str] = []
    done = threading.Event()

    def bad() -> None:
        raise RuntimeError("boom")

    def good() -> None:
        results.append("ran")
        done.set()

    runner.submit(bad)
    runner.submit(good)

    assert done.wait(timeout=2.0), "worker did not recover after exception"
    assert results == ["ran"]


def test_runner_passes_args_and_kwargs():
    runner = _MonitorRunner()

    captured: list[tuple] = []
    done = threading.Event()

    def task(*args, **kwargs) -> None:
        captured.append((args, kwargs))
        done.set()

    runner.submit(task, 1, 2, foo="bar")

    assert done.wait(timeout=2.0)
    assert captured == [((1, 2), {"foo": "bar"})]


def test_runner_skips_cancelled_tasks():
    runner = _MonitorRunner()

    call_log: list[str] = []
    drained = threading.Event()

    def slow_task(name: str) -> None:
        # Hold the worker so we can cancel later submissions before they run.
        threading.Event().wait(0.05)
        call_log.append(name)

    def sentinel() -> None:
        call_log.append("sentinel")
        drained.set()

    # First task occupies the worker; cancel the second; third should still run.
    runner.submit(slow_task, "first")
    cancel_me = runner.submit(slow_task, "should-not-run")
    cancel_me.cancel()
    runner.submit(sentinel)

    assert drained.wait(timeout=2.0), "runner did not reach sentinel"
    assert call_log == ["first", "sentinel"]


def test_runner_submit_returns_token_for_each_call():
    runner = _MonitorRunner()
    t1 = runner.submit(lambda: None)
    t2 = runner.submit(lambda: None)
    assert t1 is not t2
    assert not t1.is_cancelled
    t1.cancel()
    assert t1.is_cancelled
    assert not t2.is_cancelled
