"""Unit tests for logger helper."""

from chat_saude.observability.logger import get_logger


def test_get_logger_returns_logger():
    """Returns a named logger instance."""
    logger = get_logger("chat_saude.test")
    assert logger.name == "chat_saude.test"
