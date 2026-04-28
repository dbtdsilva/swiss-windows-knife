import threading

from src.base.monitor_runner import _MonitorRunner


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
