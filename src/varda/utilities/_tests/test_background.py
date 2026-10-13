"""Background work runs off the GUI thread and reports back on it."""

import threading

from varda.utilities.background import onMainThread, runInBackground


def test_the_task_runs_on_a_worker_and_its_result_arrives_on_the_gui_thread(qtbot):
    taskThreads, doneThreads, results = [], [], []

    def task() -> int:
        taskThreads.append(threading.current_thread())
        return 42

    def done(result: int) -> None:
        doneThreads.append(threading.current_thread())
        results.append(result)

    runInBackground(task, done, lambda error: None)
    qtbot.waitUntil(lambda: results == [42])
    assert taskThreads[0] is not threading.main_thread()
    assert doneThreads[0] is threading.main_thread()


def test_a_failure_arrives_with_its_exception(qtbot):
    errors = []

    def task() -> None:
        raise ValueError("bad band")

    runInBackground(task, lambda _result: None, errors.append)
    qtbot.waitUntil(lambda: len(errors) == 1)
    assert isinstance(errors[0], ValueError) and str(errors[0]) == "bad band"


def test_progress_reaches_the_gui_thread_in_order_before_the_result(qtbot):
    events = []

    def record(percent: int, message: str) -> None:
        events.append((percent, message, threading.current_thread()))

    report = onMainThread(record)

    def task() -> str:
        for percent in (10, 50, 90):
            report(percent, "working")
        return "done"

    runInBackground(task, lambda result: events.append(result), lambda error: None)
    qtbot.waitUntil(lambda: "done" in events)
    assert [e[0] for e in events[:-1]] == [10, 50, 90]
    assert all(e[2] is threading.main_thread() for e in events[:-1])
    assert events[-1] == "done"
