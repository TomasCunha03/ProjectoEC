import logging


def _configure_root_logger() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


_configure_root_logger()


def get_logger(name: str):
    return logging.getLogger(name)
