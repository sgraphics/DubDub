from dataclasses import dataclass
from datetime import timedelta
import pysrt
import chardet
import re
import os
from pathlib import Path

@dataclass
class SubtitleEntry:
    start_time: float  # in seconds
    end_time: float    # in seconds
    text: str

class SubtitleProcessor:
    def parse_srt(self, srt_path: str):
        """Parse SRT or ASS/SSA file with encoding detection"""
        # Detect if it's ASS/SSA format based on extension or content
        is_ass = False
        file_ext = os.path.splitext(srt_path)[1].lower()
        
        if file_ext in ['.ass', '.ssa']:
            is_ass = True
        else:
            # Check content for ASS format markers
            with open(srt_path, 'rb') as file:
                first_bytes = file.read(4096)  # Read first 4KB
                if b'[Script Info]' in first_bytes or b'Format:' in first_bytes:
                    is_ass = True
        
        if is_ass:
            print(f"Detected ASS/SSA subtitle format")
            return self._parse_ass(srt_path)
        
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
    
    def _parse_ass(self, ass_path: str):
        """Parse ASS/SSA subtitle file"""
        # Detect encoding
        with open(ass_path, 'rb') as file:
            raw_data = file.read()
            detected = chardet.detect(raw_data)
            encoding = detected['encoding']
        
        # Read file with detected encoding
        try:
            with open(ass_path, 'r', encoding=encoding) as file:
                content = file.read()
        except UnicodeDecodeError:
            # Try common fallback encodings
            for enc in ['utf-8', 'cp1252', 'iso-8859-1']:
                try:
                    with open(ass_path, 'r', encoding=enc) as file:
                        content = file.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Could not decode ASS file with any common encoding.")
        
        # Find the Events section which contains dialogues
        events_section = re.search(r'\[Events\](.*?)(?=\[|$)', content, re.DOTALL)
        if not events_section:
            print("No Events section found in ASS file")
            return []
        
        events_content = events_section.group(1)
        
        # Find the Format line to understand column order
        format_match = re.search(r'Format:(.*?)$', events_content, re.MULTILINE)
        if not format_match:
            print("No Format line found in Events section")
            return []
        
        # Parse the format to get column indices
        format_columns = [col.strip() for col in format_match.group(1).split(',')]
        start_idx = format_columns.index('Start') if 'Start' in format_columns else None
        end_idx = format_columns.index('End') if 'End' in format_columns else None
        text_idx = format_columns.index('Text') if 'Text' in format_columns else None
        
        if start_idx is None or end_idx is None or text_idx is None:
            print(f"Missing required columns in format: {format_columns}")
            return []
        
        # Extract dialogue lines
        dialogue_pattern = r'Dialogue:(.*?)$'
        dialogue_lines = re.findall(dialogue_pattern, events_content, re.MULTILINE)
        
        result = []
        for line in dialogue_lines:
            columns = self._split_ass_line(line)
            
            if len(columns) <= max(start_idx, end_idx, text_idx):
                continue  # Skip malformed lines
                
            start_time = self._ass_time_to_seconds(columns[start_idx].strip())
            end_time = self._ass_time_to_seconds(columns[end_idx].strip())
            text = self._clean_ass_text(columns[text_idx].strip())
            
            if text:  # Skip empty lines
                result.append(SubtitleEntry(
                    start_time=start_time,
                    end_time=end_time,
                    text=text
                ))
        
        print(f"Parsed {len(result)} dialogue entries from ASS file")
        return result
    
    def _split_ass_line(self, line):
        """Split ASS line by commas, respecting commas in curly braces {}"""
        parts = []
        current = ""
        in_braces = False
        
        for char in line:
            if char == '{':
                in_braces = True
                current += char
            elif char == '}':
                in_braces = False
                current += char
            elif char == ',' and not in_braces:
                parts.append(current)
                current = ""
            else:
                current += char
        
        if current:
            parts.append(current)
            
        return parts
    
    def _clean_ass_text(self, text):
        """Remove ASS style codes"""
        # Remove drawing commands
        text = re.sub(r'{.*?}', '', text)
        # Remove newline codes
        text = text.replace('\\N', ' ').replace('\\n', ' ')
        return text.strip()
    
    def _ass_time_to_seconds(self, time_str):
        """Convert ASS time format (H:MM:SS.cc) to seconds"""
        try:
            h, m, s = time_str.split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)
        except ValueError as e:
            print(f"Error parsing ASS time '{time_str}': {e}")
            return 0
    
    def _time_to_seconds(self, time) -> float:
        return time.hours * 3600 + time.minutes * 60 + time.seconds + time.milliseconds / 1000 