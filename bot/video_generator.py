"""MpaiBot Video Generator - Lyric video frame generation using Pillow."""
import io
import logging
import os
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from bot.audio_streamer import SongInfo
from bot.lyric_fetcher import LyricLine

logger = logging.getLogger("mpaibot")

# Font path for cross-platform rendering.
# Download NotoSans-Regular.ttf from https://fonts.google.com/noto/specimen/Noto+Sans
# and place it in assets/fonts/NotoSans-Regular.ttf
FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "fonts", "NotoSans-Regular.ttf"
)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load NotoSans font at the given size, falling back to Pillow's default if not found.

    Users should download NotoSans-Regular.ttf to assets/fonts/ for best results.
    See: https://fonts.google.com/noto/specimen/Noto+Sans
    """
    if os.path.isfile(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    else:
        logger.warning(
            "Font file not found at %s. Using Pillow default font. "
            "Download NotoSans-Regular.ttf to assets/fonts/ for proper rendering.",
            FONT_PATH,
        )
        # Pillow's load_default returns a basic bitmap font; we try truetype size if available
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            # Older Pillow versions don't support size parameter
            return ImageFont.load_default()


def find_current_line(lyrics: List[LyricLine], elapsed_ms: int) -> int:
    """Binary search for the current lyric line based on elapsed time.

    Returns the index of the lyric line with the largest timestamp_ms <= elapsed_ms.
    Returns -1 if no lyric line has started yet (all timestamps are > elapsed_ms).

    This is a standalone function so it can be tested independently.
    """
    left, right = 0, len(lyrics) - 1
    result = -1
    while left <= right:
        mid = (left + right) // 2
        if lyrics[mid].timestamp_ms <= elapsed_ms:
            result = mid
            left = mid + 1
        else:
            right = mid - 1
    return result


class VideoGenerator:
    """Generates video frames showing lyrics synchronized with audio playback.

    Uses Pillow to render text on a dark background. Current lyric is displayed
    prominently in the center, with the next lyric shown below in a dimmer style.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.font_large = _load_font(48)
        self.font_small = _load_font(32)
        self.bg_color = (30, 30, 40)
        self.text_color = (255, 255, 255)
        self.dim_color = (128, 128, 140)

    def generate_frame(
        self, current_line: str, next_line: Optional[str], song_info: SongInfo
    ) -> bytes:
        """Generate a single video frame with current and next lyric.

        Args:
            current_line: The current lyric text to display prominently.
            next_line: The next upcoming lyric text (displayed dimmer), or None.
            song_info: Metadata about the currently playing song.

        Returns:
            PNG image bytes for the frame.
        """
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Draw current lyric (centered, prominent)
        draw.text(
            (self.width // 2, self.height // 2),
            current_line,
            font=self.font_large,
            fill=self.text_color,
            anchor="mm",
        )

        # Draw next lyric (below, dimmer)
        if next_line:
            draw.text(
                (self.width // 2, self.height // 2 + 80),
                next_line,
                font=self.font_small,
                fill=self.dim_color,
                anchor="mm",
            )

        # Convert to PNG bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def generate_static_frame(self, song_info: SongInfo) -> bytes:
        """Generate a static frame when lyrics are unavailable.

        Displays the song title and artist name centered on the dark background.

        Args:
            song_info: Metadata about the currently playing song.

        Returns:
            PNG image bytes for the static frame.
        """
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Draw song title (prominent, centered)
        draw.text(
            (self.width // 2, self.height // 2 - 30),
            song_info.title,
            font=self.font_large,
            fill=self.text_color,
            anchor="mm",
        )

        # Draw artist name (below title, dimmer)
        draw.text(
            (self.width // 2, self.height // 2 + 40),
            song_info.artist,
            font=self.font_small,
            fill=self.dim_color,
            anchor="mm",
        )

        # Convert to PNG bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
