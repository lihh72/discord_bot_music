# Requirements Document

## Introduction

Discord music bot ("MpaiBot") yang dapat streaming musik di voice channel dengan fitur screen sharing untuk menampilkan lirik secara real-time mengikuti timestamp lagu. Bot menggunakan command prefix "mpai!" dan di-deploy di VPS pengguna. Bot mendukung pencarian dan download musik dari berbagai platform menggunakan library musicdl, serta mengambil lirik sinkron dari LRCLib API.

## Glossary

- **MpaiBot**: Discord bot aplikasi yang mengelola streaming musik dan tampilan lirik
- **Voice_Channel**: Channel suara Discord tempat bot melakukan streaming audio
- **Commander**: Pengguna Discord yang mengirimkan command ke bot
- **Lyric_Display**: Komponen visual yang menampilkan lirik lagu secara sinkron dengan audio
- **LRC_Format**: Format lirik bertimestamp dengan pola `[mm:ss.xx] teks lirik`
- **Music_Source**: Platform musik yang didukung oleh musicdl (Netease, QQ Music, Kugou, Kuwo, Migu, Spotify, YouTube, SoundCloud, dll.)
- **Screen_Share**: Fitur Discord Go Live yang digunakan bot untuk menampilkan video lirik ke voice channel
- **VPS**: Virtual Private Server dengan Ubuntu 24 tempat bot di-deploy dan dijalankan
- **Development_Environment**: PC Windows yang digunakan untuk development
- **GitHub_Repository**: Repository GitHub untuk version control dan deployment
- **Music_Downloader**: Modul yang menggunakan library musicdl untuk mencari dan mengunduh lagu
- **Lyric_Fetcher**: Modul yang mengambil lirik sinkron dari LRCLib API
- **Video_Generator**: Modul yang menghasilkan video/stream visual berisi lirik bertimestamp

## Requirements

### Requirement 1: Voice Channel Connection

**User Story:** Sebagai Commander, saya ingin bot bergabung ke voice channel yang sedang saya gunakan, sehingga saya dapat mendengarkan musik tanpa harus berpindah channel.

#### Acceptance Criteria

1. WHEN the Commander issues the `mpai!play` command, THE MpaiBot SHALL join the Voice_Channel where the Commander is currently connected
2. IF the Commander is not connected to any Voice_Channel, THEN THE MpaiBot SHALL reply with an error message indicating the Commander must join a Voice_Channel first
3. WHILE the MpaiBot is connected to a Voice_Channel and no audio is playing for more than 5 minutes, THE MpaiBot SHALL disconnect from the Voice_Channel automatically
4. WHEN the Commander issues the `mpai!leave` command, THE MpaiBot SHALL disconnect from the Voice_Channel immediately

### Requirement 2: Music Search and Download

**User Story:** Sebagai Commander, saya ingin mencari dan memutar lagu berdasarkan query teks, sehingga saya dapat mendengarkan lagu yang saya inginkan.

#### Acceptance Criteria

1. WHEN the Commander issues `mpai!play {query}`, THE Music_Downloader SHALL search for the song across available Music_Source platforms
2. WHEN multiple results are found, THE MpaiBot SHALL select the best matching result and begin downloading
3. WHEN the download completes, THE MpaiBot SHALL begin audio streaming to the Voice_Channel within 3 seconds
4. IF no results are found for the given query, THEN THE MpaiBot SHALL reply with a message indicating no songs were found
5. IF the download fails, THEN THE MpaiBot SHALL reply with an error message and suggest the Commander try a different query

### Requirement 3: Audio Streaming

**User Story:** Sebagai Commander, saya ingin bot memutar audio berkualitas baik di voice channel, sehingga saya dapat menikmati musik dengan jelas.

#### Acceptance Criteria

1. WHILE the MpaiBot is streaming audio, THE MpaiBot SHALL maintain continuous playback without interruption
2. THE MpaiBot SHALL stream audio at a bitrate of at least 128kbps to the Voice_Channel
3. WHEN the Commander issues `mpai!pause`, THE MpaiBot SHALL pause the current audio playback
4. WHEN the Commander issues `mpai!resume`, THE MpaiBot SHALL resume audio playback from the paused position
5. WHEN the Commander issues `mpai!skip`, THE MpaiBot SHALL stop the current song and play the next song in the queue
6. WHEN the current song finishes playing, THE MpaiBot SHALL automatically play the next song in the queue if available

### Requirement 4: Synced Lyric Fetching

**User Story:** Sebagai Commander, saya ingin bot mengambil lirik yang sinkron dengan timestamp, sehingga lirik dapat ditampilkan sesuai waktu lagu.

#### Acceptance Criteria

1. WHEN a song begins playing, THE Lyric_Fetcher SHALL search for synced lyrics from LRCLib API using the song title and artist name
2. WHEN synced lyrics in LRC_Format are found, THE Lyric_Fetcher SHALL parse the timestamps and lyric lines into a structured format
3. IF no synced lyrics are found, THEN THE MpaiBot SHALL display a static message indicating lyrics are unavailable
4. THE Lyric_Fetcher SHALL complete the lyric search within 5 seconds of the song starting

### Requirement 5: Real-Time Lyric Display via Screen Share

**User Story:** Sebagai Commander, saya ingin melihat lirik lagu secara real-time melalui screen share di voice channel, sehingga saya dan anggota lain dapat mengikuti lirik sambil mendengarkan musik.

#### Acceptance Criteria

1. WHEN a song with synced lyrics starts playing, THE Video_Generator SHALL generate a visual stream displaying the current lyric line
2. WHILE audio is playing, THE Lyric_Display SHALL highlight the current lyric line synchronized with the audio timestamp within a tolerance of 100 milliseconds
3. THE MpaiBot SHALL broadcast the Lyric_Display via Screen_Share (Discord Go Live) to the Voice_Channel
4. WHEN the lyric timestamp advances to the next line, THE Lyric_Display SHALL transition to display the next lyric line
5. THE Lyric_Display SHALL show the current lyric line prominently and display the next upcoming line in a dimmer style
6. IF lyrics are unavailable, THEN THE Lyric_Display SHALL show the song title and artist name as a static visual

### Requirement 6: Queue Management

**User Story:** Sebagai Commander, saya ingin mengelola antrian lagu, sehingga saya dapat memutar beberapa lagu secara berurutan.

#### Acceptance Criteria

1. WHEN the Commander issues `mpai!play {query}` while a song is already playing, THE MpaiBot SHALL add the new song to the end of the queue
2. WHEN the Commander issues `mpai!queue`, THE MpaiBot SHALL display the current queue with song titles and positions
3. WHEN the Commander issues `mpai!clear`, THE MpaiBot SHALL remove all songs from the queue
4. THE MpaiBot SHALL support a queue of at least 50 songs

### Requirement 7: Command Handling

**User Story:** Sebagai Commander, saya ingin menggunakan command dengan prefix "mpai!" yang mudah diingat, sehingga saya dapat mengontrol bot dengan cepat.

#### Acceptance Criteria

1. THE MpaiBot SHALL recognize commands with the prefix `mpai!` followed by the command name
2. WHEN an unrecognized command is issued with the `mpai!` prefix, THE MpaiBot SHALL reply with a help message listing available commands
3. THE MpaiBot SHALL support the following commands: `play`, `pause`, `resume`, `skip`, `leave`, `queue`, `clear`, `nowplaying`
4. WHEN the Commander issues `mpai!nowplaying`, THE MpaiBot SHALL display the currently playing song title, artist, and elapsed time

### Requirement 8: Cross-Platform Compatibility and Deployment

**User Story:** Sebagai pemilik bot, saya ingin mengembangkan bot di Windows dan men-deploy di VPS Ubuntu 24, sehingga bot dapat berjalan stabil di kedua environment.

#### Acceptance Criteria

1. THE MpaiBot SHALL run consistently on both Windows and Ubuntu 24 without platform-specific code modifications
2. THE MpaiBot SHALL use cross-platform compatible dependencies that work on both Windows and Linux
3. THE MpaiBot SHALL use environment variables for configuration (Discord token, API keys) to support different environments
4. THE MpaiBot SHALL include a requirements file or package manifest that enables reproducible installation on both platforms
5. THE MpaiBot SHALL run as a background service on the VPS using systemd on Ubuntu 24
6. THE MpaiBot SHALL automatically reconnect to Discord Gateway if the connection is lost
7. THE MpaiBot SHALL log operational events including errors, connections, and command usage to a log file
8. IF the MpaiBot process crashes, THEN systemd SHALL restart the MpaiBot within 10 seconds

### Requirement 9: GitHub Repository and Version Control

**User Story:** Sebagai pemilik bot, saya ingin menyimpan kode di GitHub, sehingga saya dapat mengelola versi dan melakukan deployment dari repository.

#### Acceptance Criteria

1. THE MpaiBot project SHALL include a `.gitignore` file that excludes sensitive files (environment variables, downloaded audio cache, virtual environments)
2. THE MpaiBot project SHALL include a README file with setup instructions for both Windows and Ubuntu 24
3. THE MpaiBot project SHALL include deployment instructions for pulling from GitHub and running on the VPS
4. THE MpaiBot project SHALL NOT store Discord tokens or API keys in the GitHub_Repository
