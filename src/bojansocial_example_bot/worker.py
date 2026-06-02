import logging
import threading
from queue import Queue
from typing import Callable, Optional

logger = logging.getLogger("bojansocial_py")

class WorkerPool:
    """fixed pool of threads that drain a shared job queue."""

    def __init__(self, num_workers: int):
        self._queue: Queue[Optional[Callable]] = Queue()
        self._workers: list[threading.Thread] = []
        for i in range(num_workers):
            t = threading.Thread(target=self._run, name=f"worker-{i}", daemon=True)
            t.start()
            self._workers.append(t)

    def submit(self, fn: Callable, *args, **kwargs):
        self._queue.put(lambda: fn(*args, **kwargs))

    def shutdown(self):
        for _ in self._workers:
            self._queue.put(None)  # poison pill per worker
        for t in self._workers:
            t.join()

    def _run(self):
        while True:
            job = self._queue.get()
            if job is None:
                break
            try:
                job()
            except Exception:
                logger.exception("unhandled exception in worker")
            finally:
                self._queue.task_done()
