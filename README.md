# DubDub - AI Video Dubbing Tool

DubDub automatically adds AI-generated voiceovers to videos using subtitle files.

## Usage

```
python src/main.py <video_path> <subtitle_path> <output_path>
```

### Parameters:

- `<video_path>`: Path to the input video file
- `<subtitle_path>`: Path to the subtitle file (.srt format)
- `<output_path>`: Path where the dubbed video will be saved

### Example:

```
python src/main.py "C:\Videos\Movie.mp4" "C:\Videos\Movie.srt" "output.mp4"
```

## Features

- Automatically generates voice audio from subtitles
- Mixes the generated speech with the original audio
- Detects lyrics and preserves them in the final output
- Processes subtitles in parallel for faster performance 