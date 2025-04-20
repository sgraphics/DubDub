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
        
        # Store the mixing information for later - no longer care about lyrics_mode
        self.mix_inputs.append({
            'file': short_path,
            'start': start_time,
            'duration': duration
        })
        
        return duration

    def save_final_audio(self) -> Path:
        """Process audio in batches using compressed formats"""
        print("Mixing final audio...")
        start_time = time.time()
        
        # Sort all segments by start time
        sorted_inputs = sorted(self.mix_inputs, key=lambda x: x['start'])
        
        # Output path for final audio
        output_path = self.temp_dir / "final_audio.ac3"
        
        # Create a temporary file for the processed voiceovers
        voiceover_track = self.temp_dir / "voiceovers.m4a"
        
        # Get maximum duration
        max_duration = max([mix['start'] + mix['duration'] for mix in self.mix_inputs]) + 5
        
        # Create silent base audio (using AAC)
        silent_base = self.temp_dir / "silence.m4a"
        if not silent_base.exists():
            subprocess.run([
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', f'anullsrc=r=48000:cl=stereo',
                '-t', str(max_duration),
                '-c:a', 'aac',
                '-b:a', '192k',
                str(silent_base)
            ], check=True)
        
        # First, create a track with just the voiceovers
        print("Creating voiceover track...")
        
        # Process in batches to avoid command line length limitations
        batch_size = 50
        temp_segments = []
        
        total_batches = (len(sorted_inputs) + batch_size - 1) // batch_size
        print(f"Processing {len(sorted_inputs)} segments in {total_batches} batches")
        
        for batch_idx in range(0, len(sorted_inputs), batch_size):
            batch = sorted_inputs[batch_idx:batch_idx + batch_size]
            batch_output = self.temp_dir / f"voiceover_batch_{batch_idx}.m4a"
            
            # Add all voiceovers to silent base
            batch_cmd = ['ffmpeg', '-y', '-i', str(silent_base)]
            
            filter_parts = []
            for i, mix in enumerate(batch):
                batch_cmd.extend(['-i', str(mix['file'])])
                # Place each voiceover at its timestamp at full volume
                filter_parts.append(f"[{i+1}:a]adelay={int(mix['start']*1000)}|{int(mix['start']*1000)},volume=0dB[v{i}];")
            
            # Mix all voiceovers onto silent base
            stream_refs = ''.join([f'[v{i}]' for i in range(len(batch))])
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
                temp_segments.append(batch_output)
            except subprocess.CalledProcessError as e:
                print(f"Batch processing failed: {e}")
                continue
        
        # Merge all temp segments into one track if needed
        if len(temp_segments) == 1:
            # Just use the single segment
            voiceover_track = temp_segments[0]
        elif len(temp_segments) > 1:
            # Merge all segments
            merge_cmd = ['ffmpeg', '-y']
            for segment in temp_segments:
                merge_cmd.extend(['-i', str(segment)])
                
            merge_cmd.extend([
                '-filter_complex', f'amix=inputs={len(temp_segments)}:normalize=0[out]',
                '-map', '[out]',
                '-c:a', 'aac',
                '-b:a', '192k',
                str(voiceover_track)
            ])
            
            try:
                subprocess.run(merge_cmd, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Merging segments failed: {e}")
                # Use the first segment as fallback
                if temp_segments:
                    voiceover_track = temp_segments[0]
        
        # Now create the final audio by mixing original audio with 80% volume during voiceover
        if os.path.exists(str(voiceover_track)):
            print("Creating final audio by mixing original with volume-adjusted voiceovers...")
            
            # Create volume dip track for original audio - only reduce volume during voiceovers
            final_cmd = [
                'ffmpeg', '-y',
                '-i', str(self.orig_audio),      # Original audio
                '-i', str(voiceover_track),      # Voiceover track
                '-filter_complex',
                # Use the voiceover track to create a volume control track
                '[1:a]volume=0,aeval=1*gt(val(0),0.001)[voiceover_map];' +
                # Use that map to adjust original audio volume - 0.8 when voiceover is present, 1.0 otherwise
                '[0:a][voiceover_map]volume=volume=0.8:eval=frame:enable=between(t,0,{duration})[lowered_orig];'.format(duration=max_duration) +
                # Mix the lowered original with the voiceovers
                '[lowered_orig][1:a]amix=inputs=2:normalize=0[out]',
                '-map', '[out]',
                '-c:a', 'ac3',
                '-b:a', '192k',
                str(output_path)
            ]
            
            try:
                subprocess.run(final_cmd, check=True)
                print(f"Final audio processing completed in {time.time() - start_time:.2f} seconds")
                return output_path
            except subprocess.CalledProcessError as e:
                print(f"Final processing failed: {e}")
                # Fall back to simpler method
        
        # Fallback - simple mix if the advanced method failed
        print("Using simple mix as fallback...")
        fallback_cmd = [
            'ffmpeg', '-y',
            '-i', str(self.orig_audio),
            '-i', str(voiceover_track) if os.path.exists(str(voiceover_track)) else str(silent_base),
            '-filter_complex', 'amix=inputs=2:normalize=0[out]',
            '-map', '[out]',
            '-c:a', 'ac3',
            '-b:a', '192k',
            str(output_path)
        ]
        
        subprocess.run(fallback_cmd, check=True)
        print(f"Fallback audio processing completed in {time.time() - start_time:.2f} seconds")
        return output_path

    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Warning: Could not clean up temp dir {self.temp_dir}: {e}") 