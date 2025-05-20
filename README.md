# DubDub - AI Video Dubbing Tool

DubDub automatically adds AI-generated voiceovers to videos using subtitle files.

## Installation

### 1. Python Dependencies
Install the required Python packages:
```
pip install -r requirements.txt
```

### 2. FFmpeg
Install FFmpeg (required for video and audio processing):
```
choco install ffmpeg
```
Or download from [FFmpeg official website](https://ffmpeg.org/download.html).

### 3. MKVToolNix
Install MKVToolNix (required for processing MKV files and subtitles):
```
choco install mkvtoolnix
```
Or download from [MKVToolNix website](https://mkvtoolnix.download/downloads.html).

**Note:** Make sure MKVToolNix is installed to the default location (`C:\Program Files\MKVToolNix\`).

## Usage

```
python src/main.py <video_path> <subtitle_path_or_language_code> <output_path> [--language LANG]
```

### Parameters:

- `<video_path>`: Path to the input video file
- `<subtitle_path_or_language_code>`: Path to the subtitle file (.srt format) OR language code to extract subtitles from MKV
- `<output_path>`: Path where the dubbed video will be saved
- `--language` or `-l`: Language code for TTS (default: et)

### Examples:

Basic usage with default Estonian language:
```
python src/main.py "C:\Videos\Movie.mp4" "C:\Videos\Movie.srt" "output.mkv"
```

Specify a different language (e.g., French):
```
python src/main.py "C:\Videos\Movie.mp4" "C:\Videos\Movie.srt" "output.mkv" --language fr
```

Extract subtitles from MKV using language code:
```
python src/main.py "C:\Videos\Movie.mkv" "et" "output.mkv"
```

Extract French subtitles from MKV and dub to German:
```
python src/main.py "C:\Videos\Movie.mkv" "fr" "output.mkv" --language de
```

## Features

- Automatically generates voice audio from subtitles
- Supports multiple languages through gTTS
- Mixes the generated speech with the original audio
- Detects lyrics and preserves them in the final output
- Processes subtitles in parallel for faster performance
- Handles long file paths and names
- Outputs to MKV format for best compatibility
- Can extract subtitles directly from MKV files using language codes

## Supported Languages

The tool uses Google Text-to-Speech (gTTS) for voice generation. For a list of supported languages and their codes, visit:
https://gtts.readthedocs.io/en/latest/module.html#languages-gtts-supports 