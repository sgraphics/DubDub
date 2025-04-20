# DubDub - AI Video Dubbing Tool

DubDub automatically adds AI-generated voiceovers to videos using subtitle files.

## Usage

```
python src/main.py <video_path> <subtitle_path> <output_path> [--language LANG]
```

### Parameters:

- `<video_path>`: Path to the input video file
- `<subtitle_path>`: Path to the subtitle file (.srt format)
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

## Features

- Automatically generates voice audio from subtitles
- Supports multiple languages through gTTS
- Mixes the generated speech with the original audio
- Detects lyrics and preserves them in the final output
- Processes subtitles in parallel for faster performance
- Handles long file paths and names
- Outputs to MKV format for best compatibility

## Supported Languages

The tool uses Google Text-to-Speech (gTTS) for voice generation. For a list of supported languages and their codes, visit:
https://gtts.readthedocs.io/en/latest/module.html#languages-gtts-supports 