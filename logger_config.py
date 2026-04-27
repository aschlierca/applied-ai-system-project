from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List

_memory_logs: List[str] = []


class _MemoryHandler(logging.Handler):
    """Logging handler that keeps recent records in a module-level list."""

    def __init__(self, max_records: int = 300) -> None:
        super().__init__()
        self._max = max_records

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        _memory_logs.append(msg)
        if len(_memory_logs) > self._max:
            _memory_logs.pop(0)


def get_memory_logs() -> List[str]:
    """Return a copy of all in-memory log records (newest last)."""
    return list(_memory_logs)


def setup_logger(name: str) -> logging.Logger:
    """Return a logger with a file handler and an in-memory handler (idempotent)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    Path("logs").mkdir(exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s | %(name)-22s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    log_path = Path("logs") / f"pawpal_{datetime.now().strftime('%Y%m%d')}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    mh = _MemoryHandler()
    mh.setLevel(logging.INFO)
    mh.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(mh)
    return logger
