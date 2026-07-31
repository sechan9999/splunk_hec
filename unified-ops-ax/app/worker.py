"""Event-bus worker — drains the transactional outbox (`Activity.dispatched`)
on an interval and fires subscribed agents. Two ways to run:

  - in-process thread, auto-started on app startup when EVENT_WORKER_ENABLED=1
  - standalone process:  python -m app.worker

The poller works on any DB and is idempotent (dispatched flag). Production can
upgrade to a push broker (Postgres LISTEN/NOTIFY or Redis Streams) behind the
same `dispatch_pending` drain — the outbox stays the source of truth."""
from __future__ import annotations

import logging
import threading

from app.config import get_settings
from app.events.dispatch import dispatch_pending

logger = logging.getLogger(__name__)


class EventWorker:
    def __init__(self, session_factory, interval: float = 2.0) -> None:
        self._session_factory = session_factory
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.stats = {"cycles": 0, "processed": 0, "triggered": 0, "failed": 0, "last_error": None}

    def run_once(self) -> dict:
        try:
            result = dispatch_pending(self._session_factory)
        except Exception as exc:  # keep the loop alive on transient DB errors
            logger.warning("event worker cycle failed: %s", exc)
            self.stats["last_error"] = str(exc)[:200]
            return {"processed": 0, "triggered": 0, "failed": 0}
        self.stats["cycles"] += 1
        self.stats["processed"] += result["processed"]
        self.stats["triggered"] += result["triggered"]
        self.stats["failed"] += result.get("failed", 0)
        return result

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self._interval)

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="event-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())


_WORKER: EventWorker | None = None


def get_worker() -> EventWorker:
    global _WORKER
    if _WORKER is None:
        from app.db import SessionLocal

        _WORKER = EventWorker(SessionLocal, get_settings().event_worker_interval)
    return _WORKER


def run_forever() -> None:  # pragma: no cover - standalone process entrypoint
    import time

    from app.db import SessionLocal, init_db

    init_db()
    interval = get_settings().event_worker_interval
    print(f"[event-worker] started (interval={interval}s) — Ctrl+C to stop")
    try:
        while True:
            result = dispatch_pending(SessionLocal)
            if result["processed"]:
                print(f"[event-worker] drained {result['processed']} (triggered {result['triggered']}, "
                      f"failed {result['failed']})")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[event-worker] stopped")


if __name__ == "__main__":  # pragma: no cover
    run_forever()
