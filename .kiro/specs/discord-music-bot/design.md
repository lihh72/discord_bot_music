# Design Document: Discord Music Bot (MpaiBot)

## Overview

MpaiBot adalah Discord bot berbasis Python yang streaming musik di voice channel dengan tampilan lirik real-time via screen share. Arsitektur menggunakan discord.py untuk interaksi Discord, musicdl untuk pencarian/download musik, LRCLib API untuk lirik sinkron, dan FFmpeg untuk audio/video processing.

## Architecture

### Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Runtime | Python 3.11+ | Cross-platform, rich Discord ecosystem |
| Discord Library | discord.py (v2.x) | Mature, supports voice + Go Live streaming |
| Music Download | musicdl (CharlesPikachu) | Multi-platform search, lightweight |
| Audio Processing | FFmpeg | Industry standard, cross-platform |
| Video Generation | Pillow + FFmpeg | Frame generation + video encoding |
| Lyrics API | LRCLib (lrclib.net) | Free, synced lyrics in LRC format |
| Process Manager | systemd (Ubuntu) | Native Linux service management |
| Config | python-dotenv | Environment variable management |
| Logging | Python logging module | Built-in, configurable |

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      MpaiBot                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                  │
│  │   Command    │    │    Queue     │                  │
│  │   Handler    │───▶│   Manager    │                  │
│  └──────┬───────┘    └──────┬───────┘                  │
│         │                    │                          │
│         ▼                    ▼                          │
│  ┌──────────────┐    ┌──────────────┐                  │
│  │    Music     │    │    Audio     │                  │
│  │  Downloader  │───▶│   Streamer   │──▶ Voice Channel │
│  └──────────────┘    └──────┬───────┘                  │
│                             │                          │
│  ┌──────────────┐    ┌──────┴───────┐                  │
│  │    Lyric     │───▶│    Video     │──▶ Screen Share  │
│  │   Fetcher    │    │  Generator   │                  │
│  └──────────────┘    └──────────────┘                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Project Structure

```
discord_bot_music/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point, bot initialization
│   ├── config.py            # Configuration from environment variables
│   ├── commands.py          # Command handler (mpai! prefix)
│   ├── music_downloader.py  # Music search and download via musicdl
│   ├── audio_streamer.py    # Voice connection and audio playback
│   ├── lyric_fetcher.py     # LRCLib API integration and LRC parser
│   ├── video_generator.py   # Lyric video frame generation
│   ├── screen_share.py      # Discord Go Live streaming
│   └── queue_manager.py     # Song queue management
├── tests/
│   ├── __init__.py
│   ├── test_commands.py
│   ├── test_lyric_parser.py
│   ├── test_queue_manager.py
│   └── test_video_generator.py
├── assets/
│   └── fonts/
│       └── NotoSans-Regular.ttf  # Cross-platform font
├── .env.example             # Template for environment variables
├── .gitignore
├── requirements.txt
├── README.md
├── mpaibot.service          # systemd service file
└── run.py                   # Simple runner script
```

## Component Design

### 1. Command Handler (`commands.py`)

Handles message parsing and command routing with the `mpai!` prefix.

```python
# Command registry pattern
COMMANDS = {
    "play": handle_play,
    "pause": handle_pause,
    "resume": handle_resume,
    "skip": handle_skip,
    "leave": handle_leave,
    "queue": handle_queue,
    "clear": handle_clear,
    "nowplaying": handle_nowplaying,
}

async def on_message(message):
    if not message.content.startswith("mpai!"):
        return
    command_name = message.content[5:].split()[0]
    args = message.content[5:].split()[1:]
    handler = COMMANDS.get(command_name, handle_unknown)
    await handler(message, args)
```

**Correctness Property (P1 - Command Parsing):** For any message string starting with "mpai!" followed by a known command name, the command handler SHALL route to the correct handler function. For any message with "mpai!" followed by an unknown command, it SHALL route to the help handler.

### 2. Music Downloader (`music_downloader.py`)

Wraps musicdl library for search and download operations.

```python
class MusicDownloader:
    def __init__(self, download_dir: str):
        self.download_dir = download_dir
        self.config = {
            "logfilepath": "musicdl.log",
            "savedir": download_dir,
            "search_size_per_source": 5,
            "proxies": {}
        }

    async def search_and_download(self, query: str) -> Optional[SongInfo]:
        """Search across platforms and download best match."""
        # Run musicdl in thread pool to avoid blocking
        results = await asyncio.to_thread(self._search, query)
        if not results:
            return None
        best = self._select_best(results)
        filepath = await asyncio.to_thread(self._download, best)
        return SongInfo(title=best.title, artist=best.artist, filepath=filepath)
```

### 3. Audio Streamer (`audio_streamer.py`)

Manages voice connection and FFmpeg-based audio playback.

```python
class AudioStreamer:
    def __init__(self, bot):
        self.bot = bot
        self.voice_client: Optional[VoiceClient] = None
        self.current_song: Optional[SongInfo] = None
        self.start_time: Optional[float] = None
        self.idle_timer: Optional[asyncio.Task] = None

    async def connect(self, channel: VoiceChannel):
        """Connect to voice channel."""
        self.voice_client = await channel.connect()
        self._reset_idle_timer()

    async def play(self, song: SongInfo, after_callback):
        """Stream audio file via FFmpeg at 128kbps+."""
        source = FFmpegPCMAudio(
            song.filepath,
            options="-b:a 128k"
        )
        self.voice_client.play(source, after=after_callback)
        self.start_time = time.time()
        self.current_song = song

    def get_elapsed_time(self) -> float:
        """Get current playback position in seconds."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
```

### 4. Lyric Fetcher (`lyric_fetcher.py`)

Fetches and parses synced lyrics from LRCLib API.

```python
@dataclass
class LyricLine:
    timestamp_ms: int  # Milliseconds from start
    text: str

class LyricFetcher:
    API_URL = "https://lrclib.net/api/search"

    async def fetch_lyrics(self, title: str, artist: str) -> Optional[List[LyricLine]]:
        """Fetch synced lyrics from LRCLib."""
        async with aiohttp.ClientSession() as session:
            params = {"track_name": title, "artist_name": artist}
            async with session.get(self.API_URL, params=params, timeout=5) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data:
                    return None
                synced = data[0].get("syncedLyrics")
                if not synced:
                    return None
                return self.parse_lrc(synced)

    def parse_lrc(self, lrc_text: str) -> List[LyricLine]:
        """Parse LRC format into structured lyric lines."""
        lines = []
        for line in lrc_text.strip().split("\n"):
            match = re.match(r"\[(\d+):(\d+)\.(\d+)\](.*)", line)
            if match:
                minutes, seconds, centiseconds, text = match.groups()
                timestamp_ms = (int(minutes) * 60 + int(seconds)) * 1000 + int(centiseconds) * 10
                lines.append(LyricLine(timestamp_ms=timestamp_ms, text=text.strip()))
        return lines
```

**Correctness Property (P2 - LRC Round-Trip):** For any valid list of LyricLine objects, formatting them back to LRC text and then parsing that text SHALL produce an equivalent list of LyricLine objects (round-trip property).

**Correctness Property (P3 - LRC Timestamp Ordering):** For any valid LRC text, the parsed output SHALL have timestamps in non-decreasing order.

### 5. Video Generator (`video_generator.py`)

Generates video frames showing lyrics synchronized with audio playback.

```python
class VideoGenerator:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height
        self.font_large = ImageFont.truetype("assets/fonts/NotoSans-Regular.ttf", 48)
        self.font_small = ImageFont.truetype("assets/fonts/NotoSans-Regular.ttf", 32)
        self.bg_color = (30, 30, 40)
        self.text_color = (255, 255, 255)
        self.dim_color = (128, 128, 140)

    def generate_frame(self, current_line: str, next_line: Optional[str], song_info: SongInfo) -> bytes:
        """Generate a single video frame with current and next lyric."""
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)

        # Draw current lyric (centered, prominent)
        draw.text((self.width // 2, self.height // 2), current_line,
                  font=self.font_large, fill=self.text_color, anchor="mm")

        # Draw next lyric (below, dimmer)
        if next_line:
            draw.text((self.width // 2, self.height // 2 + 80), next_line,
                      font=self.font_small, fill=self.dim_color, anchor="mm")

        # Convert to bytes for FFmpeg pipe
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
```

**Correctness Property (P4 - Lyric Sync Accuracy):** For any given playback timestamp T and a list of LyricLines, the selected current lyric line SHALL be the one with the largest timestamp_ms that is less than or equal to T. The tolerance between audio position and displayed lyric SHALL be within 100 milliseconds.

### 6. Screen Share (`screen_share.py`)

Manages Discord Go Live streaming with the generated lyric video.

```python
class ScreenShareStreamer:
    def __init__(self, voice_client, video_generator: VideoGenerator):
        self.voice_client = voice_client
        self.video_generator = video_generator
        self.streaming = False
        self._stream_task: Optional[asyncio.Task] = None

    async def start_stream(self, lyrics: List[LyricLine], song_info: SongInfo, get_elapsed: Callable):
        """Start screen share with lyric display."""
        self.streaming = True
        self._stream_task = asyncio.create_task(
            self._stream_loop(lyrics, song_info, get_elapsed)
        )

    async def _stream_loop(self, lyrics: List[LyricLine], song_info: SongInfo, get_elapsed: Callable):
        """Main loop: generate frames and push to Discord stream."""
        while self.streaming:
            elapsed_ms = int(get_elapsed() * 1000)
            current_idx = self._find_current_line(lyrics, elapsed_ms)
            current_text = lyrics[current_idx].text if current_idx >= 0 else ""
            next_text = lyrics[current_idx + 1].text if current_idx + 1 < len(lyrics) else None

            frame = self.video_generator.generate_frame(current_text, next_text, song_info)
            await self._push_frame(frame)
            await asyncio.sleep(0.05)  # 20 FPS

    def _find_current_line(self, lyrics: List[LyricLine], elapsed_ms: int) -> int:
        """Binary search for current lyric line based on timestamp."""
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
```

### 7. Queue Manager (`queue_manager.py`)

Manages the song queue with FIFO ordering.

```python
class QueueManager:
    MAX_SIZE = 50

    def __init__(self):
        self._queue: deque[SongInfo] = deque(maxlen=self.MAX_SIZE)
        self._current: Optional[SongInfo] = None

    def add(self, song: SongInfo) -> bool:
        """Add song to queue. Returns False if queue is full."""
        if len(self._queue) >= self.MAX_SIZE:
            return False
        self._queue.append(song)
        return True

    def next(self) -> Optional[SongInfo]:
        """Get next song from queue."""
        if not self._queue:
            return None
        self._current = self._queue.popleft()
        return self._current

    def clear(self):
        """Clear all songs from queue."""
        self._queue.clear()

    def get_list(self) -> List[SongInfo]:
        """Get current queue as list."""
        return list(self._queue)

    @property
    def size(self) -> int:
        return len(self._queue)
```

**Correctness Property (P5 - Queue Invariant):** After adding N songs to an empty queue, the queue size SHALL equal N (up to MAX_SIZE). After calling next() on a queue of size N (N > 0), the queue size SHALL equal N - 1. After clear(), the queue size SHALL equal 0.

**Correctness Property (P6 - Queue FIFO Order):** Songs SHALL be dequeued in the same order they were enqueued. For any sequence of N songs added, calling next() N times SHALL return them in the original insertion order.

### 8. Configuration (`config.py`)

```python
from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    COMMAND_PREFIX = "mpai!"
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
    LOG_FILE = os.getenv("LOG_FILE", "./mpaibot.log")
    IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "300"))  # 5 minutes
    FRAME_RATE = 20  # FPS for lyric video
    VIDEO_WIDTH = 1280
    VIDEO_HEIGHT = 720
```

## Data Flow

### Play Command Flow

```
Commander: mpai!play never gonna give you up
    │
    ▼
Command Handler: parse command + args
    │
    ▼
Voice Connection: join Commander's voice channel (if not already)
    │
    ▼
Music Downloader: search musicdl → select best → download file
    │
    ├──▶ Audio Streamer: FFmpeg → Voice Channel (audio)
    │
    ▼
Lyric Fetcher: LRCLib API → parse LRC
    │
    ▼
Video Generator + Screen Share: generate frames → Go Live (video)
    │
    ▼
Sync Loop: elapsed time → find current lyric → update frame (20 FPS)
```

## Deployment Design

### systemd Service File (`mpaibot.service`)

```ini
[Unit]
Description=MpaiBot Discord Music Bot
After=network.target

[Service]
Type=simple
User=mpaibot
WorkingDirectory=/opt/mpaibot
ExecStart=/opt/mpaibot/venv/bin/python run.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### Deployment Steps (Ubuntu 24 VPS)

1. Clone from GitHub repository
2. Create virtual environment and install dependencies
3. Configure `.env` with Discord token
4. Install FFmpeg (`apt install ffmpeg`)
5. Copy systemd service file and enable
6. Start service

## Correctness Properties Summary

| ID | Property | Type | Requirement |
|----|----------|------|-------------|
| P1 | Command parsing routes correctly | Property | 7.1, 7.2 |
| P2 | LRC parse/format round-trip | Round-trip | 4.2 |
| P3 | LRC timestamps non-decreasing | Invariant | 4.2 |
| P4 | Lyric sync within 100ms tolerance | Metamorphic | 5.2 |
| P5 | Queue size invariant after operations | Invariant | 6.1, 6.3, 6.4 |
| P6 | Queue FIFO ordering preserved | Property | 6.1 |

## Error Handling Strategy

| Scenario | Handling |
|----------|----------|
| Commander not in voice channel | Reply with error message |
| No search results | Reply "no songs found" |
| Download failure | Reply with error, suggest retry |
| LRCLib API timeout/failure | Show static visual (title + artist) |
| FFmpeg crash | Log error, skip to next song |
| Discord connection lost | Auto-reconnect via discord.py |
| Queue full (50 songs) | Reply with "queue full" message |

## Dependencies

```
discord.py[voice]>=2.3.0
musicdl>=0.0.1
aiohttp>=3.9.0
Pillow>=10.0.0
python-dotenv>=1.0.0
PyNaCl>=1.5.0
```

System dependencies:
- FFmpeg (required for audio/video processing)
- Python 3.11+
