"""MpaiBot Audio Streamer - Voice connection and audio playback management."""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import discord
from discord import FFmpegPCMAudio, VoiceChannel, VoiceClient

from bot.config import Config

logger = logging.getLogger("mpaibot")


@dataclass
class SongInfo:
    """Holds metadata for a song."""
    title: str
    artist: str
    filepath: str
    duration: float  # Duration in seconds


class AudioStreamer:
    """Manages voice connection and FFmpeg-based audio playback for a single guild.

    Implements per-guild singleton pattern via get_streamer() class method.
    Handles connecting/disconnecting from voice channels, playing/pausing/resuming/skipping
    audio, idle timeout auto-disconnect, and elapsed time tracking.
    """

    _instances: Dict[int, "AudioStreamer"] = {}

    def __init__(self, bot: discord.Client, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.voice_client: Optional[VoiceClient] = None
        self.current_song: Optional[SongInfo] = None
        self.start_time: Optional[float] = None
        self.pause_start: Optional[float] = None
        self.total_paused_duration: float = 0.0
        self.idle_timer: Optional[asyncio.Task] = None
        self._after_callback: Optional[Callable] = None

    @classmethod
    def get_streamer(cls, bot: discord.Client, guild_id: int) -> "AudioStreamer":
        """Get or create an AudioStreamer instance for a guild (per-guild singleton)."""
        if guild_id not in cls._instances:
            cls._instances[guild_id] = cls(bot, guild_id)
        return cls._instances[guild_id]

    @classmethod
    def remove_streamer(cls, guild_id: int) -> None:
        """Remove the streamer instance for a guild."""
        cls._instances.pop(guild_id, None)

    # --- Connection Management ---

    async def connect(self, channel: VoiceChannel) -> None:
        """Connect to a voice channel.

        Validates: Requirement 1.1 - Bot joins Commander's voice channel.
        """
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel.id == channel.id:
                return  # Already in the same channel
            await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect()
        self._reset_idle_timer()
        logger.info("Connected to voice channel: %s (guild: %s)", channel.name, self.guild_id)

    async def disconnect(self) -> None:
        """Disconnect from the voice channel.

        Validates: Requirement 1.4 - mpai!leave disconnects immediately.
        """
        self._cancel_idle_timer()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            logger.info("Disconnected from voice channel (guild: %s)", self.guild_id)
        self.voice_client = None
        self.current_song = None
        self.start_time = None
        self.pause_start = None
        self.total_paused_duration = 0.0
        AudioStreamer.remove_streamer(self.guild_id)

    @property
    def is_connected(self) -> bool:
        """Check if the bot is connected to a voice channel."""
        return self.voice_client is not None and self.voice_client.is_connected()

    # --- Playback Control ---

    async def play(self, song: SongInfo, after_callback: Optional[Callable] = None) -> None:
        """Stream audio file via FFmpeg at 128kbps.

        Validates: Requirement 3.1 - Continuous playback without interruption.
        Validates: Requirement 3.2 - 128kbps minimum bitrate.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to a voice channel")

        self._cancel_idle_timer()
        self._after_callback = after_callback

        source = FFmpegPCMAudio(
            song.filepath,
            options="-b:a 128k"
        )

        def _after_play(error):
            """Callback invoked when playback finishes or errors.

            Validates: Requirement 3.6 - Auto-play next song when current finishes.
            """
            if error:
                logger.error("Playback error for '%s': %s", song.title, error)
            else:
                logger.info("Finished playing: %s", song.title)

            self.current_song = None
            self.start_time = None
            self.pause_start = None
            self.total_paused_duration = 0.0
            self._reset_idle_timer()

            if after_callback:
                # Schedule the async callback on the event loop
                asyncio.run_coroutine_threadsafe(
                    after_callback(error), self.bot.loop
                )

        self.voice_client.play(source, after=_after_play)
        self.start_time = time.time()
        self.total_paused_duration = 0.0
        self.pause_start = None
        self.current_song = song
        logger.info("Now playing: %s - %s", song.title, song.artist)

    def pause(self) -> bool:
        """Pause the current audio playback.

        Validates: Requirement 3.3 - pause command.
        Returns True if successfully paused, False otherwise.
        """
        if not self.voice_client or not self.voice_client.is_playing():
            return False
        self.voice_client.pause()
        self.pause_start = time.time()
        logger.info("Paused playback: %s", self.current_song.title if self.current_song else "unknown")
        return True

    def resume(self) -> bool:
        """Resume audio playback from the paused position.

        Validates: Requirement 3.4 - resume command.
        Returns True if successfully resumed, False otherwise.
        """
        if not self.voice_client or not self.voice_client.is_paused():
            return False
        self.voice_client.resume()
        # Track total paused duration for accurate elapsed time
        if self.pause_start is not None:
            self.total_paused_duration += time.time() - self.pause_start
            self.pause_start = None
        self._cancel_idle_timer()
        logger.info("Resumed playback: %s", self.current_song.title if self.current_song else "unknown")
        return True

    def skip(self) -> bool:
        """Stop the current song to trigger the after callback for next song.

        Validates: Requirement 3.5 - skip command (stop current, play next).
        The after callback will handle playing the next song in the queue.
        """
        if not self.voice_client:
            return False
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()  # This triggers the after callback
            logger.info("Skipped: %s", self.current_song.title if self.current_song else "unknown")
            return True
        return False

    # --- Elapsed Time Tracking ---

    def get_elapsed_time(self) -> float:
        """Get current playback position in seconds, accounting for pauses.

        Validates: Requirement 7.4 (nowplaying elapsed time).
        """
        if self.start_time is None:
            return 0.0
        now = time.time()
        elapsed = now - self.start_time - self.total_paused_duration
        # If currently paused, subtract the ongoing pause duration
        if self.pause_start is not None:
            elapsed -= (now - self.pause_start)
        return max(0.0, elapsed)

    # --- Idle Timeout ---

    def _reset_idle_timer(self) -> None:
        """Reset the idle disconnect timer.

        Validates: Requirement 1.3 - Auto-disconnect after 5 min idle.
        Uses call_soon_threadsafe to safely schedule from any context.
        """
        self._cancel_idle_timer()
        loop = self.bot.loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(self._create_idle_task)

    def _create_idle_task(self) -> None:
        """Create the idle timer task (must be called from the event loop thread)."""
        self.idle_timer = asyncio.ensure_future(self._idle_disconnect())

    def _cancel_idle_timer(self) -> None:
        """Cancel the current idle timer if running."""
        if self.idle_timer and not self.idle_timer.done():
            self.idle_timer.cancel()
            self.idle_timer = None

    async def _idle_disconnect(self) -> None:
        """Wait for IDLE_TIMEOUT seconds then disconnect if still idle."""
        try:
            await asyncio.sleep(Config.IDLE_TIMEOUT)
            # Only disconnect if not currently playing
            if self.voice_client and not self.voice_client.is_playing():
                logger.info("Idle timeout reached, disconnecting (guild: %s)", self.guild_id)
                await self.disconnect()
        except asyncio.CancelledError:
            pass  # Timer was cancelled, no action needed
