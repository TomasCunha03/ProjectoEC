"""
Logging configuration module.

Provides a single call-site (``get_logger``) for every module in the package.
The root logger is configured once at import time so that third-party libraries
that use the standard ``logging`` module automatically inherit the same format.
"""

import logging


def _configure_root_logger() -> None:
    """Configure the root logger with a timestamped format if not already set up.

    The guard on ``root.handlers`` prevents duplicate handler registration when
    the module is imported multiple times (e.g. during testing or hot-reload).
    """
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


# Configure logging at import time so callers never need to think about setup.
_configure_root_logger()


def get_logger(name: str):
    """Return a standard library logger scoped to *name*.

    Callers should pass ``__name__`` so log records show the originating module.
    """
    return logging.getLogger(name)
