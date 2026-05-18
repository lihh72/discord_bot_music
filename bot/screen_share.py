"""MpaiBot Screen Share Streamer - Discord Go Live streaming for lyric display."""
import asyncio
import logging
from typing import Callable, List, Optional

from bot.audio_streamer import SongInfo
from bot.lyric_fetcher import LyricLine
from bot.video_generator import VideoGenerator, find_current_line

logger = logging.getLogger("mpaibot")


class ScreenShareStreamer:
    """Manages Discord Go Live streaming with generated lyric video frames.

    Runs an async loop at 20 FPS that:
    1. Gets the current elapsed playback time
    2. Finds the current lyric line via binary search
    3. Generates a video frame with current + next lyric
    4. Pushes the frame to Discord's screen share

    Note: discord.py does NOT have a public Go Live/screen share API.
    The _push_frame method is a no-op stub. Frame generation and lyric sync
    logic work correctly for when a Go Live library becomes available.
    """

    def __init__(self, voice_client, video_generator: VideoGenerator):
        self.voice_client = voice_client
        self.video_generator = video_generator
        self.streaming = False
        self._stream_task: Optional[asyncio.Task] = None

    async def start_stream(
        self,
        lyrics: List[LyricLine],
        song_info: SongInfo,
        get_elapsed: Callable[[], float],
    ) -> None:
        """Start screen share with lyric display.

        Launches the frame generation loop as an async task.

        Args:
            lyrics: List of timestamped lyric lines (may be empty).
            song_info: Metadata about the currently playing song.
            get_elapsed: Callable that returns current playback position in seconds.
        """
        self.streaming = True
        self._stream_task = asyncio.create_task(
            self._stream_loop(lyrics, song_info, get_elapsed)
        )
        logger.info("Screen share stream started for: %s - %s", song_info.title, song_info.artist)

    async def _stream_loop(
        self,
        lyrics: List[LyricLine],
        song_info: SongInfo,
        get_elapsed: Callable[[], float],
    ) -> None:
        """Main loop: generate frames at 20 FPS and push to Discord stream.

        For each frame:
        - Get elapsed time from the audio streamer
        - Find the current lyric line using binary search
        - Generate a video frame with current and next lyric text
        - Push the frame to Discord's screen share

        If lyrics list is empty, generates a static frame with title + artist.
        """
        try:
            while self.streaming:
                if not lyrics:
                    # No lyrics available - show static frame with title + artist
                    frame = self.video_generator.generate_static_frame(song_info)
                else:
                    elapsed_ms = int(get_elapsed() * 1000)
                    current_idx = find_current_line(lyrics, elapsed_ms)
                    current_text = lyrics[current_idx].text if current_idx >= 0 else ""
                    next_text = (
                        lyrics[current_idx + 1].text
                        if current_idx + 1 < len(lyrics)
                        else None
                    )
                    frame = self.video_generator.generate_frame(
                        current_text, next_text, song_info
                    )

                await self._push_frame(frame)
                await asyncio.sleep(0.05)  # 20 FPS (1/20 = 0.05s per frame)
        except asyncio.CancelledError:
            logger.info("Screen share stream loop cancelled")
        except Exception as e:
            logger.error("Error in screen share stream loop: %s", e)
        finally:
            self.streaming = False

    async def stop_stream(self) -> None:
        """Cleanly stop the streaming task.

        Cancels the running stream loop task and waits for it to finish.
        """
        self.streaming = False
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        self._stream_task = None
        logger.info("Screen share stream stopped")

    async def _push_frame(self, frame: bytes) -> None:
        """Push a video frame to Discord's screen share.

        TODO: Implement when a Discord Go Live / screen share library becomes available.
        discord.py does NOT currently expose a public API for Go Live streaming.
        This method is a no-op stub that logs at debug level.

        When a compatible library is available, this method should:
        1. Encode the PNG frame to a video stream format
        2. Push it to the Discord voice connection's video channel

        Args:
            frame: PNG image bytes to broadcast.
        """
        # No-op stub - discord.py lacks Go Live API support
        logger.debug("Frame generated (%d bytes) - Go Live API not available", len(frame))
