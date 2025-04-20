from dataclasses import dataclass
from datetime import timedelta
import pysrt
import chardet

@dataclass
class SubtitleEntry:
    start_time: float  # in seconds
    end_time: float    # in seconds
    text: str

class SubtitleProcessor:
    def parse_srt(self, srt_path: str):
        """Parse SRT file with encoding detection"""
        # First, detect the file's encoding
        with open(srt_path, 'rb') as file:
            raw_data = file.read()
            detected = chardet.detect(raw_data)
            encoding = detected['encoding']
            
        print(f"Detected subtitle encoding: {encoding}")
            
        # Try the detected encoding first
        try:
            subs = pysrt.open(srt_path, encoding=encoding)
        except Exception as e:
            print(f"Failed with detected encoding {encoding}, trying common fallbacks...")
            
            # If that fails, try common encodings
            encodings_to_try = ['utf-8', 'cp1252', 'iso-8859-1', 'latin1', 'ascii']
            
            for enc in encodings_to_try:
                try:
                    print(f"Trying encoding: {enc}")
                    subs = pysrt.open(srt_path, encoding=enc)
                    break
                except Exception as e:
                    continue
            else:
                # If all fails, raise the last error
                raise ValueError(f"Could not read SRT file with any common encoding. Please check the file encoding. Last detected encoding was: {encoding}")
        
        # Convert pysrt subtitles to our SubtitleEntry objects
        return [
            SubtitleEntry(
                start_time=self._time_to_seconds(sub.start),
                end_time=self._time_to_seconds(sub.end),
                text=sub.text
            )
            for sub in subs
        ]
    
    def _time_to_seconds(self, time) -> float:
        return time.hours * 3600 + time.minutes * 60 + time.seconds + time.milliseconds / 1000 