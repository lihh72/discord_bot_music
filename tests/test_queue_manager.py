"""Tests for QueueManager - unit tests and property-based tests."""
import asyncio
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from bot.audio_streamer import SongInfo
from bot.queue_manager import QueueManager


# --- Strategies ---

def song_info_strategy():
    """Generate arbitrary SongInfo instances for property testing."""
    return st.builds(
        SongInfo,
        title=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            blacklist_characters="\x00"
        )),
        artist=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            blacklist_characters="\x00"
        )),
        filepath=st.text(min_size=1, max_size=100, alphabet=st.characters(
            whitelist_categories=("L", "N", "P"),
            blacklist_characters="\x00"
        )),
        duration=st.floats(min_value=0.1, max_value=600.0, allow_nan=False, allow_infinity=False),
    )


# --- Unit Tests ---

class TestQueueManagerUnit:
    """Unit tests for QueueManager basic functionality."""

    def setup_method(self):
        """Create a fresh QueueManager for each test."""
        self.queue = QueueManager()

    def test_initial_state_empty(self):
        """New queue should be empty."""
        assert self.queue.size == 0
        assert self.queue.get_list() == []

    def test_add_single_song(self):
        """Adding a song should increase size to 1."""
        song = SongInfo(title="Test", artist="Artist", filepath="/tmp/test.mp3", duration=180.0)
        result = self.queue.add(song)
        assert result is True
        assert self.queue.size == 1

    def test_add_returns_false_when_full(self):
        """Adding to a full queue should return False."""
        for i in range(QueueManager.MAX_SIZE):
            song = SongInfo(title=f"Song {i}", artist="Artist", filepath=f"/tmp/{i}.mp3", duration=180.0)
            self.queue.add(song)

        extra = SongInfo(title="Extra", artist="Artist", filepath="/tmp/extra.mp3", duration=180.0)
        result = self.queue.add(extra)
        assert result is False
        assert self.queue.size == QueueManager.MAX_SIZE

    def test_next_returns_first_song(self):
        """next() should return the first song added (FIFO)."""
        song1 = SongInfo(title="First", artist="A", filepath="/tmp/1.mp3", duration=100.0)
        song2 = SongInfo(title="Second", artist="B", filepath="/tmp/2.mp3", duration=200.0)
        self.queue.add(song1)
        self.queue.add(song2)

        result = self.queue.next()
        assert result == song1

    def test_next_on_empty_returns_none(self):
        """next() on empty queue should return None."""
        result = self.queue.next()
        assert result is None

    def test_clear_empties_queue(self):
        """clear() should remove all songs."""
        for i in range(5):
            song = SongInfo(title=f"Song {i}", artist="Artist", filepath=f"/tmp/{i}.mp3", duration=180.0)
            self.queue.add(song)

        self.queue.clear()
        assert self.queue.size == 0
        assert self.queue.get_list() == []

    def test_get_list_returns_copy(self):
        """get_list() should return a list copy of the queue."""
        song = SongInfo(title="Test", artist="Artist", filepath="/tmp/test.mp3", duration=180.0)
        self.queue.add(song)
        result = self.queue.get_list()
        assert result == [song]
        # Modifying the returned list should not affect the queue
        result.clear()
        assert self.queue.size == 1

    def test_per_guild_singleton(self):
        """get_queue() should return same instance for same guild_id."""
        # Clear class-level instances for test isolation
        QueueManager._instances.clear()
        q1 = QueueManager.get_queue(123)
        q2 = QueueManager.get_queue(123)
        q3 = QueueManager.get_queue(456)
        assert q1 is q2
        assert q1 is not q3
        QueueManager._instances.clear()


# --- Command Handler Tests ---

class TestQueueCommandHandler:
    """Unit tests for mpai!queue and mpai!clear command handlers."""

    def setup_method(self):
        """Clear singleton instances before each test."""
        QueueManager._instances.clear()

    def teardown_method(self):
        """Clear singleton instances after each test."""
        QueueManager._instances.clear()

    @pytest.mark.asyncio
    async def test_handle_queue_empty(self):
        """mpai!queue should show 'Queue is empty' when no songs."""
        from bot.commands import handle_queue

        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 1001
        message.channel.send = AsyncMock()

        await handle_queue(message, [])

        message.channel.send.assert_called_once_with("Queue is empty.")

    @pytest.mark.asyncio
    async def test_handle_queue_with_songs(self):
        """mpai!queue should display numbered list of songs."""
        from bot.commands import handle_queue

        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 1002
        message.channel.send = AsyncMock()

        queue = QueueManager.get_queue(1002)
        queue.add(SongInfo(title="Song A", artist="Artist 1", filepath="/tmp/a.mp3", duration=180.0))
        queue.add(SongInfo(title="Song B", artist="Artist 2", filepath="/tmp/b.mp3", duration=200.0))

        await handle_queue(message, [])

        sent_text = message.channel.send.call_args[0][0]
        assert "1. Song A - Artist 1" in sent_text
        assert "2. Song B - Artist 2" in sent_text

    @pytest.mark.asyncio
    async def test_handle_clear(self):
        """mpai!clear should clear the queue and confirm."""
        from bot.commands import handle_clear

        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 1003
        message.channel.send = AsyncMock()

        queue = QueueManager.get_queue(1003)
        queue.add(SongInfo(title="Song", artist="Artist", filepath="/tmp/s.mp3", duration=180.0))

        await handle_clear(message, [])

        assert queue.size == 0
        message.channel.send.assert_called_once_with("🗑️ Queue cleared.")


# --- Property-Based Tests ---

class TestQueueSizeInvariant:
    """Property test for queue size invariant (P5).

    **Validates: Requirements 6.1, 6.3, 6.4**

    P5 (Queue Size Invariant): After adding N songs to an empty queue, size == N
    (up to MAX_SIZE). After next() on queue of size N>0, size == N-1.
    After clear(), size == 0.
    """

    @given(songs=st.lists(song_info_strategy(), min_size=0, max_size=50))
    @settings(max_examples=200)
    def test_size_equals_n_after_adding_n_songs(self, songs):
        """After adding N songs to an empty queue, size == min(N, MAX_SIZE).

        **Validates: Requirements 6.1, 6.4**
        """
        queue = QueueManager()
        added_count = 0
        for song in songs:
            if queue.add(song):
                added_count += 1

        expected_size = min(len(songs), QueueManager.MAX_SIZE)
        assert queue.size == expected_size
        assert queue.size == added_count

    @given(songs=st.lists(song_info_strategy(), min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_size_decreases_by_one_after_next(self, songs):
        """After next() on queue of size N>0, size == N-1.

        **Validates: Requirements 6.1, 6.4**
        """
        queue = QueueManager()
        for song in songs:
            queue.add(song)

        size_before = queue.size
        result = queue.next()
        assert result is not None
        assert queue.size == size_before - 1

    @given(songs=st.lists(song_info_strategy(), min_size=0, max_size=50))
    @settings(max_examples=200)
    def test_size_zero_after_clear(self, songs):
        """After clear(), size == 0 regardless of previous state.

        **Validates: Requirements 6.3**
        """
        queue = QueueManager()
        for song in songs:
            queue.add(song)

        queue.clear()
        assert queue.size == 0


class TestQueueFIFOOrder:
    """Property test for queue FIFO ordering (P6).

    **Validates: Requirements 6.1**

    P6 (Queue FIFO Order): Songs SHALL be dequeued in the same order they were
    enqueued. For any sequence of N songs added, calling next() N times SHALL
    return them in the original insertion order.
    """

    @given(songs=st.lists(song_info_strategy(), min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_fifo_order_preserved(self, songs):
        """Songs dequeued in same order as enqueued.

        **Validates: Requirements 6.1**
        """
        queue = QueueManager()
        for song in songs:
            queue.add(song)

        dequeued = []
        while queue.size > 0:
            dequeued.append(queue.next())

        assert dequeued == songs

    @given(
        songs=st.lists(song_info_strategy(), min_size=2, max_size=50),
        split=st.integers(min_value=1, max_value=49),
    )
    @settings(max_examples=200)
    def test_partial_dequeue_preserves_order(self, songs, split):
        """Partial dequeue followed by more adds still preserves FIFO order.

        **Validates: Requirements 6.1**
        """
        assume(split < len(songs))

        queue = QueueManager()
        # Add first batch
        first_batch = songs[:split]
        for song in first_batch:
            queue.add(song)

        # Dequeue some
        dequeue_count = min(split // 2, queue.size) if split > 0 else 0
        dequeued_first = []
        for _ in range(dequeue_count):
            dequeued_first.append(queue.next())

        # Add second batch
        second_batch = songs[split:]
        for song in second_batch:
            queue.add(song)

        # Dequeue all remaining
        dequeued_rest = []
        while queue.size > 0:
            dequeued_rest.append(queue.next())

        # The full dequeue order should match the original insertion order
        all_dequeued = dequeued_first + dequeued_rest
        assert all_dequeued == songs
