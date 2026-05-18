"""MpaiBot Discord Music Bot - Main module with bot initialization and logging."""
import logging
from logging.handlers import RotatingFileHandler
import sys

import discord

from bot.config import Config
from bot.commands import on_message as commands_on_message, set_bot


def setup_logging() -> logging.Logger:
    """Configure logging with rotating file handler and console output.

    File handler: RotatingFileHandler with max 5MB per file, keeping 3 backups.
    Logs errors, connections, and command events.
    """
    logger = logging.getLogger("mpaibot")
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler - max 5MB per file, keep 3 backups
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def create_bot() -> discord.Client:
    """Create and configure the Discord bot client with required intents."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.voice_states = True

    bot = discord.Client(intents=intents)

    logger = logging.getLogger("mpaibot")

    @bot.event
    async def on_ready():
        logger.info("MpaiBot connected as %s (ID: %s)", bot.user.name, bot.user.id)
        logger.info("Connected to %d guild(s)", len(bot.guilds))
        set_bot(bot)

    @bot.event
    async def on_message(message):
        await commands_on_message(message)

    return bot


def run_bot():
    """Initialize logging, create the bot, and start the event loop."""
    logger = setup_logging()

    if not Config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set. Please configure your .env file.")
        sys.exit(1)

    bot = create_bot()
    logger.info("Starting MpaiBot...")
    # reconnect=True enables automatic Discord Gateway reconnection on disconnects
    # discord.py will handle exponential backoff and session resumption automatically
    bot.run(Config.DISCORD_TOKEN, reconnect=True, log_handler=None)
