# Tasks

## Task 1: Project Setup and Configuration

- [x] 1.1 Initialize project structure with `bot/`, `tests/`, and `assets/` directories
- [x] 1.2 Create `requirements.txt` with all Python dependencies (discord.py[voice], musicdl, aiohttp, Pillow, python-dotenv, PyNaCl)
- [x] 1.3 Create `bot/config.py` with environment variable loading using python-dotenv
- [x] 1.4 Create `.env.example` with template variables (DISCORD_TOKEN, DOWNLOAD_DIR, LOG_FILE, IDLE_TIMEOUT)
- [x] 1.5 Create `.gitignore` excluding .env, downloads/, __pycache__/, venv/, *.log
- [x] 1.6 Create `run.py` entry point script that initializes and runs the bot

## Task 2: Bot Core and Command Handler

- [x] 2.1 Create `bot/main.py` with discord.py bot initialization, intents configuration, and logging setup
- [x] 2.2 Create `bot/commands.py` with command registry pattern and `mpai!` prefix parsing
- [x] 2.3 Implement command routing: parse message, extract command name and args, route to handler
- [x] 2.4 Implement `handle_unknown` that replies with help message listing all available commands
- [x] 2.5 Write property test for command parsing: any message with "mpai!" + known command routes correctly (P1)

## Task 3: Voice Channel Connection

- [x] 3.1 Create `bot/audio_streamer.py` with `AudioStreamer` class and `connect()` method
- [x] 3.2 Implement voice channel join logic: detect Commander's current voice channel and connect
- [x] 3.3 Implement `mpai!leave` command to disconnect from voice channel
- [x] 3.4 Implement idle timeout: auto-disconnect after 5 minutes of no audio playback
- [x] 3.5 Implement error handling: reply with error if Commander is not in a voice channel

## Task 4: Music Search and Download

- [x] 4.1 Create `bot/music_downloader.py` with `MusicDownloader` class wrapping musicdl
- [x] 4.2 Implement `search_and_download()` method: search across platforms, select best match, download
- [x] 4.3 Implement `_select_best()` ranking logic for search results
- [x] 4.4 Implement error handling: no results found, download failure with user-friendly messages
- [x] 4.5 Implement async wrapper using `asyncio.to_thread()` to avoid blocking the event loop

## Task 5: Audio Streaming

- [x] 5.1 Implement `play()` method in AudioStreamer using FFmpegPCMAudio with 128kbps bitrate
- [x] 5.2 Implement `pause()` and `resume()` methods for playback control
- [x] 5.3 Implement `skip()` method that stops current song and triggers next in queue
- [x] 5.4 Implement `after` callback for auto-playing next song when current finishes
- [x] 5.5 Implement `get_elapsed_time()` method tracking playback position

## Task 6: Lyric Fetcher and LRC Parser

- [x] 6.1 Create `bot/lyric_fetcher.py` with `LyricFetcher` class and LRCLib API integration
- [x] 6.2 Implement `parse_lrc()` method: parse LRC format text into list of LyricLine objects
- [x] 6.3 Implement `format_lrc()` method: convert LyricLine list back to LRC text (for round-trip testing)
- [x] 6.4 Implement `fetch_lyrics()` with 5-second timeout and error handling
- [x] 6.5 Write property test for LRC round-trip: parse(format(lyrics)) == lyrics (P2)
- [x] 6.6 Write property test for LRC timestamp ordering: parsed output has non-decreasing timestamps (P3)

## Task 7: Video Generator for Lyric Display

- [x] 7.1 Create `bot/video_generator.py` with `VideoGenerator` class using Pillow
- [x] 7.2 Implement `generate_frame()`: render current lyric (prominent) and next lyric (dimmer) on dark background
- [x] 7.3 Implement `_find_current_line()` binary search for current lyric based on elapsed time
- [x] 7.4 Implement static frame generation for when lyrics are unavailable (show title + artist)
- [x] 7.5 Write property test for lyric sync: for any timestamp T, selected line has largest timestamp <= T (P4)
- [x] 7.6 Add NotoSans font to `assets/fonts/` for cross-platform text rendering

## Task 8: Screen Share Streaming

- [x] 8.1 Create `bot/screen_share.py` with `ScreenShareStreamer` class
- [x] 8.2 Implement `start_stream()` that launches the frame generation loop as async task
- [x] 8.3 Implement `_stream_loop()` at 20 FPS: get elapsed time → find lyric → generate frame → push to Discord
- [x] 8.4 Implement `stop_stream()` to cleanly stop the streaming task
- [x] 8.5 Integrate Discord Go Live API for broadcasting video frames to voice channel

## Task 9: Queue Manager

- [x] 9.1 Create `bot/queue_manager.py` with `QueueManager` class using deque with maxlen=50
- [x] 9.2 Implement `add()`, `next()`, `clear()`, `get_list()`, and `size` property
- [x] 9.3 Implement `mpai!queue` command handler to display queue contents
- [x] 9.4 Implement `mpai!clear` command handler to clear the queue
- [x] 9.5 Write property test for queue size invariant after add/next/clear operations (P5)
- [x] 9.6 Write property test for queue FIFO ordering (P6)

## Task 10: Integration and Play Command Flow

- [x] 10.1 Implement full `mpai!play` flow: join channel → search → download → stream audio → fetch lyrics → start screen share
- [x] 10.2 Implement `mpai!nowplaying` command showing title, artist, and elapsed time
- [x] 10.3 Implement `mpai!pause`, `mpai!resume`, `mpai!skip` command handlers with queue integration
- [x] 10.4 Wire up auto-play next song callback with lyric refresh and screen share update
- [x] 10.5 Add status messages: "Searching...", "Downloading...", "Now playing: ..." feedback to Commander

## Task 11: Deployment and Documentation

- [x] 11.1 Create `mpaibot.service` systemd unit file with auto-restart configuration
- [x] 11.2 Create `README.md` with setup instructions for Windows (development) and Ubuntu 24 (production)
- [x] 11.3 Add deployment section to README: git clone, venv setup, .env config, FFmpeg install, systemd enable
- [x] 11.4 Configure Python logging to file with rotation (errors, connections, commands)
- [x] 11.5 Implement Discord Gateway auto-reconnect handling via discord.py reconnect=True
