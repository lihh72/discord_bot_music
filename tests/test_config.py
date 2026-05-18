import os
from unittest.mock import patch


class TestConfig:
    """Tests for bot/config.py configuration loading."""

    def test_default_values(self):
        """Config should have correct default values when env vars are not set."""
        # Re-import with clean environment to test defaults
        with patch.dict(os.environ, {}, clear=True):
            # Remove cached module to force re-import
            import importlib
            import bot.config
            importlib.reload(bot.config)
            from bot.config import Config

            assert Config.COMMAND_PREFIX == "mpai!"
            assert Config.DOWNLOAD_DIR == "./downloads"
            assert Config.LOG_FILE == "./mpaibot.log"
            assert Config.IDLE_TIMEOUT == 300
            assert Config.FRAME_RATE == 20
            assert Config.VIDEO_WIDTH == 1280
            assert Config.VIDEO_HEIGHT == 720

    def test_discord_token_from_env(self):
        """Config should load DISCORD_TOKEN from environment."""
        with patch.dict(os.environ, {"DISCORD_TOKEN": "test-token-123"}):
            import importlib
            import bot.config
            importlib.reload(bot.config)
            from bot.config import Config

            assert Config.DISCORD_TOKEN == "test-token-123"

    def test_custom_download_dir(self):
        """Config should use DOWNLOAD_DIR from environment when set."""
        with patch.dict(os.environ, {"DOWNLOAD_DIR": "/custom/path"}):
            import importlib
            import bot.config
            importlib.reload(bot.config)
            from bot.config import Config

            assert Config.DOWNLOAD_DIR == "/custom/path"

    def test_custom_log_file(self):
        """Config should use LOG_FILE from environment when set."""
        with patch.dict(os.environ, {"LOG_FILE": "/var/log/mpaibot.log"}):
            import importlib
            import bot.config
            importlib.reload(bot.config)
            from bot.config import Config

            assert Config.LOG_FILE == "/var/log/mpaibot.log"

    def test_custom_idle_timeout(self):
        """Config should parse IDLE_TIMEOUT as integer from environment."""
        with patch.dict(os.environ, {"IDLE_TIMEOUT": "600"}):
            import importlib
            import bot.config
            importlib.reload(bot.config)
            from bot.config import Config

            assert Config.IDLE_TIMEOUT == 600

    def test_constant_values(self):
        """Config should have correct constant values that are not configurable."""
        from bot.config import Config

        assert Config.COMMAND_PREFIX == "mpai!"
        assert Config.FRAME_RATE == 20
        assert Config.VIDEO_WIDTH == 1280
        assert Config.VIDEO_HEIGHT == 720
