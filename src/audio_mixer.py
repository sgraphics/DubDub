from pathlib import Path
import subprocess
from typing import List, Tuple
import tempfile
import time
import os
import hashlib

class AudioMixer:
    def __init__(self):
        # Create temp directory with a short path to avoid Windows path length limitations
        temp_base = os.environ.get('TEMP', tempfile.gettempdir())
        short_dir_name = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self.temp_dir = Path(temp_base) / short_dir_name
        self.temp_dir.mkdir(exist_ok=True)
        
        self.orig_audio = None
        self.final_audio = None
        self.mix_inputs = []  # Store all TTS segments and their timing
        
    def load_video_audio(self, video_path: Path) -> None:
        """Extract full audio track from video once"""
        print("Extracting audio from video...")
        start_time = time.time()
        
        # Extract audio to temporary AAC file instead of WAV
        self.orig_audio = self.temp_dir / "orig_audio.m4a"
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vn',  # No video
            '-c:a', 'aac',  # Use AAC codec
            '-b:a', '192k',  # 192kbps bitrate
            '-ar', '48000',  # Higher sample rate
            '-ac', '2',  # Stereo
            '-y',  # Overwrite if exists
            '-strict', '-2',  # Add strict flag for experimental codecs
            str(self.orig_audio)
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"Audio extraction took {time.time() - start_time:.2f} seconds")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Error extracting audio, falling back to simpler method: {e}")
            # Try fallback method - explicitly target the second audio stream (usually AC3)
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-map', '0:a:1',  # Select second audio stream (usually AC3)
                '-vn',  # No video
                '-c:a', 'aac',  # Use AAC codec
                '-b:a', '192k',  # 192kbps bitrate
                '-ar', '48000',  # Higher sample rate
                '-ac', '2',  # Stereo
                '-y',  # Overwrite if exists
                str(self.orig_audio)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"Fallback audio extraction took {time.time() - start_time:.2f} seconds")

    def mix_audio_segment(self, video_path: Path, tts_audio: Path,
                          start_time: float, duck_level: float = 0.2, lyrics_mode: bool = False) -> float:
        """Store TTS segment info for later batch processing"""
        if self.orig_audio is None:
            self.load_video_audio(video_path)
        
        # Get duration of TTS audio
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(tts_audio)
        ]
        duration = float(subprocess.check_output(probe_cmd).decode().strip())
        
        # Check if TTS audio path is already short and accessible
        short_path = tts_audio
        if len(str(tts_audio)) > 240:
            # Path is too long, need to copy to short name
            short_name = f"tts_{len(self.mix_inputs)}.m4a"  # Use AAC instead of WAV
            short_path = self.temp_dir / short_name
            
            # Copy file to temp location with short name, converting to AAC
            print(f"Copying TTS audio to shorter path: {short_path}")
            subprocess.run([
                'ffmpeg', '-i', str(tts_audio),
                '-c:a', 'aac',  # Use AAC codec
                '-b:a', '192k',  # 192kbps bitrate
                '-y',
                str(short_path)
            ], capture_output=True, check=True)
        
        # Store the mixing information for later
        self.mix_inputs.append({
            'file': short_path,
            'start': start_time,
            'duration': duration,
            'lyrics_mode': lyrics_mode
        })
        
        return duration

    def save_final_audio(self) -> Path:
        """Try single-pass processing first, fall back to chunked if needed"""
        print("Mixing final audio...")
        start_time = time.time()
        
        # Output path for final audio
        output_path = self.temp_dir / "final_audio.ac3"
        
        # Try single-pass processing first
        try:
            # Build FFmpeg command for single-pass processing
            cmd = ['ffmpeg', '-y']
            
            # Add all input files
            cmd.extend(['-i', str(self.orig_audio)])  # Original audio
            for mix in self.mix_inputs:
                cmd.extend(['-i', str(mix['file'])])
            
            # Create filter graph
            filter_parts = []
            
            # Start with original audio
            filter_parts.append("[0:a]volume=1[orig];")
            
            # Add volume adjustment and delays for each TTS segment
            for i, mix in enumerate(self.mix_inputs, 1):
                delay_ms = int(mix['start'] * 1000)
                volume = "-5dB" if mix['lyrics_mode'] else "-8dB"
                filter_parts.append(
                    f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={volume}[v{i}];"
                )
            
            # Create mix of all streams
            streams = ['[orig]'] + [f'[v{i}]' for i in range(1, len(self.mix_inputs) + 1)]
            filter_parts.append(f"{','.join(streams)}amix=inputs={len(streams)}:normalize=0[out]")
            
            # Add filter complex and output options
            cmd.extend([
                '-filter_complex', ''.join(filter_parts),
                '-map', '[out]',
                '-c:a', 'ac3',
                '-b:a', '192k',
                '-strict', '-2',
                str(output_path)
            ])
            
            # Try single-pass processing
            print("Attempting single-pass audio processing...")
            subprocess.run(cmd, check=True)
            print(f"Single-pass audio processing successful! Took {time.time() - start_time:.2f} seconds")
            return output_path
            
        except subprocess.CalledProcessError as e:
            print(f"Single-pass processing failed: {e}")
            print("Falling back to chunked processing...")
            return self._save_final_audio_chunked()
    
    def _save_final_audio_chunked(self) -> Path:
        """Process audio in chunks when single-pass fails"""
        print(f"Using chunked audio processing for {len(self.mix_inputs)} subtitle segments")
        
        # Output path
        output_path = self.temp_dir / "final_audio.ac3"
        
        # Create silent base audio (using AAC instead of WAV)
        silent_base = self.temp_dir / "silence.m4a"
        if not silent_base.exists():
            max_duration = max([mix['start'] + mix['duration'] for mix in self.mix_inputs]) + 5
            subprocess.run([
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'anullsrc=r=48000:cl=stereo',
                '-t', str(max_duration),
                '-c:a', 'aac',
                '-b:a', '192k',
                str(silent_base)
            ], check=True)
        
        # Process in batches
        batch_size = 30
        temp_audio_segments = []
        sorted_inputs = sorted(self.mix_inputs, key=lambda x: x['start'])
        
        for batch_idx in range(0, len(sorted_inputs), batch_size):
            batch = sorted_inputs[batch_idx:batch_idx + batch_size]
            print(f"Processing batch {batch_idx//batch_size + 1}/{(len(sorted_inputs) + batch_size - 1)//batch_size}...")
            
            # Create a batch output file (using AAC)
            batch_output = self.temp_dir / f"batch_{batch_idx}.m4a"
            
            # Create batch command
            batch_cmd = [
                'ffmpeg', '-y',
                '-i', str(silent_base)
            ]
            
            # Add all input files and create filter
            filter_parts = []
            for i, mix in enumerate(batch):
                batch_cmd.extend(['-i', str(mix['file'])])
                vol = "-5dB" if mix['lyrics_mode'] else "-8dB"
                filter_parts.append(f"[{i+1}:a]adelay={int(mix['start']*1000)}|{int(mix['start']*1000)},volume={vol}[s{i}];")
            
            # Add mix for all streams
            stream_refs = ''.join([f'[s{i}]' for i in range(len(batch))])
            filter_parts.append(f"[0:a]{stream_refs}amix=inputs={len(batch)+1}:normalize=0[out]")
            
            batch_cmd.extend([
                '-filter_complex', ''.join(filter_parts),
                '-map', '[out]',
                '-c:a', 'aac',
                '-b:a', '192k',
                str(batch_output)
            ])
            
            try:
                subprocess.run(batch_cmd, check=True)
                temp_audio_segments.append(batch_output)
            except subprocess.CalledProcessError as e:
                print(f"Batch processing failed: {e}")
                continue
        
        if not temp_audio_segments:
            print("Warning: No audio segments were successfully processed. Using original audio.")
            subprocess.run([
                'ffmpeg', '-y',
                '-i', str(self.orig_audio),
                '-c:a', 'ac3',
                '-b:a', '192k',
                str(output_path)
            ], check=True)
            return output_path
        
        # Final mix of all segments with original audio
        final_cmd = [
            'ffmpeg', '-y',
            '-i', str(self.orig_audio)
        ]
        
        for segment in temp_audio_segments:
            final_cmd.extend(['-i', str(segment)])
        
        final_cmd.extend([
            '-filter_complex', f'amix=inputs={len(temp_audio_segments)+1}:normalize=0[out]',
            '-map', '[out]',
            '-c:a', 'ac3',
            '-b:a', '192k',
            '-strict', '-2',
            str(output_path)
        ])
        
        try:
            subprocess.run(final_cmd, check=True)
        except subprocess.CalledProcessError:
            print("Final mixing failed, using original audio as fallback")
            subprocess.run([
                'ffmpeg', '-y',
                '-i', str(self.orig_audio),
                '-c:a', 'ac3',
                '-b:a', '192k',
                str(output_path)
            ], check=True)
        
        return output_path

    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Warning: Could not clean up temp dir {self.temp_dir}: {e}") 