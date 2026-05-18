"""Tests for bot/main.py - bot initialization and logging setup."""
import logging
import os
import tempfile
from unittest.mock import patch

import discord

from bot.main import setup_logging, create_bot


class TestSetupLogging:
    """Tests for the logging configuration."""

    def test_returns_logger_with_correct_name(self):
        logger = setup_logging()
        assert logger.name == "mpaibot"

    def test_logger_has_file_and_console_handlers(self):
        # Clear any existing handlers first
        logger = logging.getLogger("mpaibot")
        logger.handlers.clear()

        logger = setup_logging()
        handler_types = [type(h) for h in logger.handlers]
        from logging.handlers import RotatingFileHandler
        assert RotatingFileHandler in handler_types
        assert logging.StreamHandler in handler_types

    def test_logger_level_is_info(self):
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_no_duplicate_handlers_on_repeated_calls(self):
        # Clear handlers first
        logger = logging.getLogger("mpaibot")
        logger.handlers.clear()

        setup_logging()
        handler_count = len(logging.getLogger("mpaibot").handlers)
        setup_logging()
        assert len(logging.getLogger("mpaibot").handlers) == handler_count

    def test_file_handler_uses_config_log_file(self):
        logger = logging.getLogger("mpaibot")
        logger.handlers.clear()

        with patch("bot.main.Config") as mock_config:
            mock_config.LOG_FILE = os.path.join(tempfile.gettempdir(), "test_mpaibot.log")
            logger = setup_logging()

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1

    def teardown_method(self):
        """Clean up logger handlers after each test."""
        logger = logging.getLogger("mpaibot")
        for handler in logger.handlers[:]:
            handler.close()
        logger.handlers.clear()


class TestCreateBot:
    """Tests for bot client creation."""

    def test_returns_discord_client(self):
        bot = create_bot()
        assert isinstance(bot, discord.Client)

    def test_message_content_intent_enabled(self):
        bot = create_bot()
        assert bot.intents.message_content is True

    def test_guilds_intent_enabled(self):
        bot = create_bot()
        assert bot.intents.guilds is True

    def test_voice_states_intent_enabled(self):
        bot = create_bot()
        assert bot.intents.voice_states is True
