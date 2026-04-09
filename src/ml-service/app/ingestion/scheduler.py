import logging
import threading

logger = logging.getLogger(__name__)

_timer: threading.Timer | None = None
_interval_seconds: int = 0


def _run_scheduled():
    from app.ingestion.pipeline import get_pipeline

    try:
        pipeline = get_pipeline()
        result = pipeline.run()
        logger.info(
            "Scheduled ingestion complete: fetched=%d, new=%d, embedded=%d",
            result.fetched,
            result.new,
            result.embedded,
        )
    except Exception:
        logger.exception("Scheduled ingestion failed")
    finally:
        _schedule_next()


def _schedule_next():
    global _timer
    if _interval_seconds > 0:
        _timer = threading.Timer(_interval_seconds, _run_scheduled)
        _timer.daemon = True
        _timer.start()


def start_scheduler(interval_minutes: int):
    global _interval_seconds
    _interval_seconds = interval_minutes * 60
    logger.info("Ingestion scheduler started (every %d minutes)", interval_minutes)
    _schedule_next()


def stop_scheduler():
    global _timer
    if _timer:
        _timer.cancel()
        logger.info("Ingestion scheduler stopped")
