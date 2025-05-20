import subprocess
from pathlib import Path
import tempfile
import shutil
import os
import hashlib
import time
from typing import List, Optional

class MediaProcessor:
    def __init__(self):
        # Default MKVToolNix installation path
        self.mkvmerge = r"C:\Program Files\MKVToolNix\mkvmerge.exe"
        self.mkvextract = r"C:\Program Files\MKVToolNix\mkvextract.exe"
        self._verify_mkvtoolnix()
        
        # Create temp directory with a short path to avoid Windows path length limitations
        temp_base = os.environ.get('TEMP', tempfile.gettempdir())
        short_dir_name = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self.temp_dir = Path(temp_base) / short_dir_name
        self.temp_dir.mkdir(exist_ok=True)
        
    def _verify_mkvtoolnix(self):
        try:
            result = subprocess.run([self.mkvmerge, '--version'], capture_output=True, text=True)
            print(f"MKVMerge version: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            raise RuntimeError(f"MKVToolNix not found at {self.mkvmerge}. Please install MKVToolNix first.")

    def extract_subtitles(self, video_path: Path, language_code: str) -> tuple[Optional[Path], list[str]]:
        """Extract subtitles of a specified language from an MKV file
        
        Returns:
            tuple: (subtitle_path, available_languages)
                - subtitle_path: Path to extracted subtitle file or None if extraction failed
                - available_languages: List of available subtitle language codes
        """
        print(f"Extracting {language_code} subtitles from {video_path}")
        
        # First, get info about tracks in the MKV file
        cmd = [self.mkvmerge, '-J', str(video_path)]
        available_subtitles = []
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            import json
            info = json.loads(result.stdout)
            
            # Find subtitle track with matching language
            subtitle_track_id = None
            
            for track in info.get('tracks', []):
                if track.get('type') == 'subtitles':
                    track_lang = track.get('properties', {}).get('language')
                    track_name = track.get('properties', {}).get('track_name', '')
                    track_id = track.get('id')
                    
                    # Store information about this subtitle track
                    subtitle_info = f"{track_lang}"
                    if track_name:
                        subtitle_info += f" ({track_name})"
                    available_subtitles.append(subtitle_info)
                    
                    # Check if this is the track we're looking for
                    if track_lang == language_code:
                        subtitle_track_id = track_id
                        print(f"Found {language_code} subtitle track with ID {subtitle_track_id}")
                        break
            
            if subtitle_track_id is None:
                if available_subtitles:
                    print(f"No subtitle track with language '{language_code}' found.")
                    print(f"Available subtitle languages: {', '.join(available_subtitles)}")
                    return None, available_subtitles
                else:
                    print(f"No subtitle tracks found in the video file.")
                    return None, []
            
            # Extract the subtitle track to a temporary SRT file
            temp_srt = self.temp_dir / f"subtitles_{language_code}.srt"
            extract_cmd = [
                self.mkvextract, 'tracks', str(video_path),
                f"{subtitle_track_id}:{str(temp_srt)}"
            ]
            
            subprocess.run(extract_cmd, check=True)
            
            if temp_srt.exists():
                print(f"Successfully extracted subtitles to {temp_srt}")
                return temp_srt, available_subtitles
            else:
                print(f"Failed to extract subtitles to {temp_srt}")
                return None, available_subtitles
                
        except subprocess.CalledProcessError as e:
            print(f"Error executing mkvmerge to get track info: {e}")
            return None, []
        except Exception as e:
            print(f"Error extracting subtitles: {e}")
            return None, []

    def load_video(self, video_path: str) -> Path:
        # Convert to Path object
        video_path = Path(video_path)
        
        # Check if the path is already short enough to be processed directly
        if len(str(video_path)) < 240:
            try:
                # Verify file can be read directly
                with open(video_path, 'rb') as f:
                    # Just test reading the first few bytes
                    f.read(1024)
                
                print(f"Using video directly from: {video_path}")
                return video_path
            except Exception as e:
                print(f"Cannot access video directly: {e}")
                print("Will copy to temp location instead")
        else:
            print(f"Path too long ({len(str(video_path))} chars), will copy to temp location")
        
        # If we get here, we need to copy the file to a temp location
        file_ext = video_path.suffix
        short_name = f"input{file_ext}"
        temp_video = self.temp_dir / short_name
        
        # For large files, use ffmpeg to copy instead of shutil to avoid loading into memory
        print(f"Copying video to temp location: {temp_video}")
        try:
            subprocess.run([
                'ffmpeg', '-i', str(video_path), 
                '-c', 'copy', '-y', str(temp_video)
            ], check=True)
            
            return temp_video
        except subprocess.CalledProcessError as e:
            print(f"Error copying video with ffmpeg: {e}")
            print("Trying alternative copy method...")
            
            # Try again with a more specific approach - just copy the video stream
            try:
                subprocess.run([
                    'ffmpeg', '-i', str(video_path),
                    '-map', '0:v',  # Just the video stream
                    '-c:v', 'copy',
                    '-y', str(temp_video)
                ], check=True)
                
                return temp_video
            except subprocess.CalledProcessError as e2:
                print(f"Alternative copy also failed: {e2}")
                # Last resort: try direct file copy
                shutil.copy2(video_path, temp_video)
                return temp_video

    def save_video(self, video_path: Path, dubbed_audio: Path, output_path: str, language: str = 'et'):
        """Save the final video with the dubbed audio track"""
        # Ensure output has .mkv extension for compatibility
        output_path = str(Path(output_path).with_suffix('.mkv'))
        
        # Check if output path is too long
        path_too_long = len(str(output_path)) > 240
        use_temp = path_too_long
        
        # If path is too long, use a temporary output path
        if use_temp:
            temp_output = self.temp_dir / f"output_{int(time.time())}.mkv"
        else:
            temp_output = Path(output_path)
        
        if path_too_long:
            print(f"Warning: Output path is too long ({len(str(output_path))} chars)")
            if use_temp:
                print(f"Using temporary output path: {temp_output}")
        
        # Try with mkvmerge first
        try:
            # Use mkvmerge to add the dubbed audio track and set it as default
            cmd = [
                self.mkvmerge,
                '-o', str(temp_output),
                # Video file with all streams
                str(video_path),
                # Add dubbed audio track
                '--track-name', f'0:AI Dubbed Audio ({language})',
                '--language', f'0:{language}',
                '--default-track', '0:yes',  # Set the new audio track as default
                str(dubbed_audio)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            print("\nMKVMerge output:")
            print(result.stdout)
            if result.stderr:
                print("\nMKVMerge errors:")
                print(result.stderr)
            
            if result.returncode != 0:
                raise RuntimeError(f"MKVMerge failed with return code {result.returncode}")
            
            if not temp_output.exists():
                raise RuntimeError("Output file was not created")
            
        except Exception as e:
            print(f"\nError during MKVMerge: {str(e)}")
            print("Trying ffmpeg fallback...")
            
            # Fallback to ffmpeg if mkvmerge fails
            try:
                # Use ffmpeg to create final output
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(video_path),
                    '-i', str(dubbed_audio),
                    '-map', '0:v',  # Take video from first input
                    '-map', '1:a',  # Take audio from second input (the dubbed audio)
                    '-map', '0:a',  # Also include original audio
                    '-c:v', 'copy',  # Copy video codec
                    '-c:a', 'copy',  # Copy audio codec
                    f'-metadata:s:a:0', f'title=AI Dubbed Audio ({language})',
                    f'-metadata:s:a:0', f'language={language}',
                    '-disposition:a:0', 'default',  # Set first audio (dubbed) as default
                    '-strict', '-2',  # Allow experimental codecs
                    str(temp_output)
                ]
                
                subprocess.run(ffmpeg_cmd, check=True)
                
                if not temp_output.exists():
                    raise RuntimeError("Output file was not created with ffmpeg")
                
            except subprocess.CalledProcessError as e:
                print(f"FFmpeg fallback failed: {e}")
                print("Trying simpler ffmpeg approach...")
                
                # Try one more time with a simpler approach
                try:
                    simple_cmd = [
                        'ffmpeg', '-y',
                        '-i', str(video_path),
                        '-i', str(dubbed_audio),
                        '-c', 'copy',  # Copy all streams without re-encoding
                        '-map', '0:v',  # Copy video from input
                        '-map', '1:a',  # Take dubbed audio
                        '-shortest',    # End when shortest input ends
                        '-strict', '-2',
                        str(temp_output)
                    ]
                    
                    subprocess.run(simple_cmd, check=True)
                    
                except Exception as e:
                    print(f"All merge attempts failed: {e}")
                    raise RuntimeError("Could not create output file with any method")
        
        # If we used a temporary path due to length, copy to the final destination
        if use_temp and temp_output.exists():
            print(f"Copying final output to: {output_path}")
            # Use ffmpeg to copy to final destination to handle long paths better
            try:
                subprocess.run([
                    'ffmpeg', '-i', str(temp_output),
                    '-c', 'copy', '-y', output_path
                ], check=True)
            except Exception as e:
                print(f"Error copying to final destination: {e}")
                print(f"Final output is available at: {temp_output}")
        
        print(f"Successfully created: {output_path if not use_temp or (use_temp and Path(output_path).exists()) else temp_output}")

    def cleanup(self):
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Warning: Could not clean up temp dir {self.temp_dir}: {e}")

    # Alternative method for quick testing
    def quick_test_merge(self, video_path: str, aac_audio_path: str, output_path: str):
        # Always use .mkv extension for output to support all audio formats
        if not output_path.lower().endswith(".mkv"):
            print(f"Warning: Changing output extension to .mkv to ensure compatibility")
            output_path = str(Path(output_path).with_suffix('.mkv'))
            
        cmd = [
            self.mkvmerge,
            '-o', output_path,
            str(video_path),
            '--track-name', '0:AI Dubbed Audio (Estonian)',
            '--language', '0:et',
            '--default-track', '0:yes',
            str(aac_audio_path)
        ]
        subprocess.run(cmd, check=True)
        print(f"Quick test merge completed: {output_path}") 