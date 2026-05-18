# MpaiBot - Discord Music Bot

A Discord bot that streams music in voice channels with real-time synced lyric display via screen share.

## Features

- Music search and playback from multiple platforms via musicdl
- Real-time synced lyrics display through Discord Go Live (screen share)
- Song queue management (up to 50 songs)
- Auto-disconnect after 5 minutes of idle
- Auto-reconnect to Discord Gateway on connection loss
- Runs as a systemd service on Ubuntu with auto-restart

## Commands

| Command | Description |
|---------|-------------|
| `mpai!play <query>` | Search and play a song |
| `mpai!pause` | Pause current playback |
| `mpai!resume` | Resume paused playback |
| `mpai!skip` | Skip to next song in queue |
| `mpai!leave` | Disconnect from voice channel |
| `mpai!queue` | Show current song queue |
| `mpai!clear` | Clear the song queue |
| `mpai!nowplaying` | Show current song info |

## Requirements

- Python 3.11+
- FFmpeg (for audio/video processing)
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))

## Setup - Windows (Development)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/discord_bot_music.git
cd discord_bot_music
```

### 2. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install FFmpeg

Download FFmpeg from https://ffmpeg.org/download.html and add it to your system PATH.

Alternatively, install via winget:

```bash
winget install FFmpeg
```

### 5. Configure environment

```bash
copy .env.example .env
```

Edit `.env` and set your Discord bot token:

```
DISCORD_TOKEN=your_actual_bot_token_here
```

### 6. Run the bot

```bash
python run.py
```

## Setup - Ubuntu 24 (Production)

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg git
```

### 2. Create service user

```bash
sudo useradd -r -m -d /opt/mpaibot -s /bin/bash mpaibot
```

### 3. Clone the repository

```bash
sudo -u mpaibot git clone https://github.com/your-username/discord_bot_music.git /opt/mpaibot
```

### 4. Create virtual environment and install dependencies

```bash
cd /opt/mpaibot
sudo -u mpaibot python3.11 -m venv venv
sudo -u mpaibot /opt/mpaibot/venv/bin/pip install -r requirements.txt
```

### 5. Configure environment

```bash
sudo -u mpaibot cp .env.example .env
sudo -u mpaibot nano .env
```

Set your Discord bot token and adjust paths as needed:

```
DISCORD_TOKEN=your_actual_bot_token_here
DOWNLOAD_DIR=/opt/mpaibot/downloads
LOG_FILE=/opt/mpaibot/mpaibot.log
```

### 6. Install and enable systemd service

```bash
sudo cp /opt/mpaibot/mpaibot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mpaibot
sudo systemctl start mpaibot
```

### 7. Verify the service is running

```bash
sudo systemctl status mpaibot
sudo journalctl -u mpaibot -f
```

## Deployment

### Quick Deployment Steps (Ubuntu 24 VPS)

```bash
# 1. Clone repository
git clone https://github.com/your-username/discord_bot_music.git /opt/mpaibot

# 2. Setup virtual environment
cd /opt/mpaibot
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt

# 3. Configure .env
cp .env.example .env
nano .env  # Set DISCORD_TOKEN

# 4. Install FFmpeg
sudo apt install -y ffmpeg

# 5. Enable systemd service
sudo cp mpaibot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mpaibot
sudo systemctl start mpaibot
```

### Service Management

```bash
# Start the bot
sudo systemctl start mpaibot

# Stop the bot
sudo systemctl stop mpaibot

# Restart the bot
sudo systemctl restart mpaibot

# View logs
sudo journalctl -u mpaibot -f

# Check status
sudo systemctl status mpaibot
```

### Auto-Restart Behavior

The systemd service is configured with `Restart=always` and `RestartSec=5`, meaning:
- If the bot crashes or exits unexpectedly, systemd will restart it within 5 seconds
- The bot also has built-in Discord Gateway auto-reconnect (`reconnect=True`)

### Updating

```bash
cd /opt/mpaibot
sudo -u mpaibot git pull
sudo -u mpaibot /opt/mpaibot/venv/bin/pip install -r requirements.txt
sudo systemctl restart mpaibot
```

## Logging

The bot logs to a rotating file (`mpaibot.log` by default):
- Max file size: 5 MB
- Backup files kept: 3 (mpaibot.log.1, mpaibot.log.2, mpaibot.log.3)
- Logged events: errors, connections, disconnections, commands executed

Configure the log file path via the `LOG_FILE` environment variable.

## Project Structure

```
discord_bot_music/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Bot initialization and logging
│   ├── config.py            # Configuration from .env
│   ├── commands.py          # Command handler (mpai! prefix)
│   ├── music_downloader.py  # Music search and download
│   ├── audio_streamer.py    # Voice connection and playback
│   ├── lyric_fetcher.py     # LRCLib API and LRC parser
│   ├── video_generator.py   # Lyric video frame generation
│   ├── screen_share.py      # Discord Go Live streaming
│   └── queue_manager.py     # Song queue management
├── tests/                   # Unit and property-based tests
├── assets/fonts/            # Fonts for lyric rendering
├── .env.example             # Environment variable template
├── .gitignore
├── requirements.txt
├── mpaibot.service          # systemd service file
├── run.py                   # Entry point
└── README.md
```

## License

This project is for personal/educational use.
