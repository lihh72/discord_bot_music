"""MpaiBot Queue Manager - Song queue management with FIFO ordering."""
import logging
from collections import deque
from typing import Dict, List, Optional

from bot.audio_streamer import SongInfo

logger = logging.getLogger("mpaibot")


class QueueManager:
    """Manages the song queue for a single guild with FIFO ordering.

    Implements per-guild singleton pattern via get_queue() class method.
    Supports up to MAX_SIZE songs in the queue.

    Validates: Requirement 6.1 - Add new song to end of queue when mpai!play while playing.
    Validates: Requirement 6.4 - Support queue of at least 50 songs.
    """

    MAX_SIZE = 50

    # Per-guild singleton instances
    _instances: Dict[int, "QueueManager"] = {}

    @classmethod
    def get_queue(cls, guild_id: int) -> "QueueManager":
        """Get or create a QueueManager instance for a guild."""
        if guild_id not in cls._instances:
            cls._instances[guild_id] = cls()
            logger.info("Created QueueManager for guild %s", guild_id)
        return cls._instances[guild_id]

    def __init__(self):
        self._queue: deque[SongInfo] = deque(maxlen=self.MAX_SIZE)
        self._current: Optional[SongInfo] = None

    def add(self, song: SongInfo) -> bool:
        """Add song to end of queue. Returns False if queue is full.

        Validates: Requirement 6.1 - Add new song to end of queue.
        Validates: Requirement 6.4 - Support queue of at least 50 songs.
        """
        if len(self._queue) >= self.MAX_SIZE:
            return False
        self._queue.append(song)
        return True

    def next(self) -> Optional[SongInfo]:
        """Get next song from queue (FIFO). Returns None if queue is empty."""
        if not self._queue:
            return None
        self._current = self._queue.popleft()
        return self._current

    def clear(self):
        """Clear all songs from queue.

        Validates: Requirement 6.3 - mpai!clear removes all songs from queue.
        """
        self._queue.clear()

    def get_list(self) -> List[SongInfo]:
        """Get current queue as a list."""
        return list(self._queue)

    @property
    def size(self) -> int:
        """Return current number of songs in the queue."""
        return len(self._queue)
