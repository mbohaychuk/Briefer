import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


@patch("app.ingestion.scheduler.threading.Timer")
def test_start_scheduler_sets_interval(mock_timer_cls):
    import app.ingestion.scheduler as sched

    mock_timer = MagicMock()
    mock_timer_cls.return_value = mock_timer

    sched._interval_seconds = 0
    sched.start_scheduler(10)

    assert sched._interval_seconds == 600  # 10 * 60
    mock_timer_cls.assert_called_once_with(600, sched._run_scheduled)
    assert mock_timer.daemon is True
    mock_timer.start.assert_called_once()


@patch("app.ingestion.scheduler.threading.Timer")
def test_stop_scheduler_cancels_timer(mock_timer_cls):
    import app.ingestion.scheduler as sched

    mock_timer = MagicMock()
    sched._timer = mock_timer

    sched.stop_scheduler()
    mock_timer.cancel.assert_called_once()


def test_stop_scheduler_no_timer():
    """stop_scheduler should not raise when there is no timer."""
    import app.ingestion.scheduler as sched

    sched._timer = None
    sched.stop_scheduler()  # Should not raise


@patch("app.ingestion.scheduler._schedule_next")
@patch("app.ingestion.pipeline.get_pipeline")
def test_run_scheduled_calls_pipeline(mock_get_pipeline, mock_schedule_next):
    import app.ingestion.scheduler as sched

    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = SimpleNamespace(fetched=5, new=3, embedded=3)
    mock_get_pipeline.return_value = mock_pipeline

    sched._run_scheduled()

    mock_pipeline.run.assert_called_once()
    mock_schedule_next.assert_called_once()


@patch("app.ingestion.scheduler._schedule_next")
@patch("app.ingestion.pipeline.get_pipeline")
def test_run_scheduled_handles_exception(mock_get_pipeline, mock_schedule_next, caplog):
    import app.ingestion.scheduler as sched

    mock_get_pipeline.side_effect = RuntimeError("Not initialized")

    with caplog.at_level(logging.ERROR):
        sched._run_scheduled()

    assert "Scheduled ingestion failed" in caplog.text
    # Should still schedule the next run even after failure
    mock_schedule_next.assert_called_once()


@patch("app.ingestion.scheduler.threading.Timer")
def test_schedule_next_creates_daemon_timer(mock_timer_cls):
    import app.ingestion.scheduler as sched

    mock_timer = MagicMock()
    mock_timer_cls.return_value = mock_timer

    sched._interval_seconds = 300
    sched._schedule_next()

    mock_timer_cls.assert_called_once_with(300, sched._run_scheduled)
    assert mock_timer.daemon is True
    mock_timer.start.assert_called_once()


@patch("app.ingestion.scheduler.threading.Timer")
def test_schedule_next_does_nothing_when_interval_zero(mock_timer_cls):
    import app.ingestion.scheduler as sched

    sched._interval_seconds = 0
    sched._schedule_next()

    mock_timer_cls.assert_not_called()
