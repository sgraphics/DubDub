from pathlib import Path
import subprocess
from typing import List, Tuple
import tempfile
import time

class AudioMixer:
    def __init__(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.orig_audio = None
        self.final_audio = None
        self.mix_inputs = []  # Store all TTS segments and their timing
        
    def load_video_audio(self, video_path: Path) -> None:
        """Extract full audio track from video once"""
        print("Extracting audio from video...")
        start_time = time.time()
        
        # Extract audio to temporary WAV file
        self.orig_audio = self.temp_dir / "orig_audio.wav"
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM format
            '-ar', '48000',  # Higher sample rate
            '-ac', '2',  # Stereo
            '-y',  # Overwrite if exists
            str(self.orig_audio)
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"Audio extraction took {time.time() - start_time:.2f} seconds")

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
        
        # Store the mixing information for later
        self.mix_inputs.append({
            'file': tts_audio,
            'start': start_time,
            'duration': duration,
            'lyrics_mode': lyrics_mode
        })
        
        return duration

    def save_final_audio(self) -> Path:
        """Generate complex filter graph and mix all audio at once"""
        print("Mixing final audio...")
        start_time = time.time()
        
        # Prepare filter graph
        filter_complex = []
        input_count = len(self.mix_inputs) + 1  # +1 for original audio
        
        # Start with original audio
        filter_complex.append("[0:a]volume=1[orig];")
        
        # Add volume adjustment and delays for each TTS segment
        for i, mix in enumerate(self.mix_inputs, 1):
            delay_ms = int(mix['start'] * 1000)
            volume = "-5dB" if mix['lyrics_mode'] else "-8dB"  # TTS volume adjustment
            
            # Add input with delay and volume adjustment
            filter_complex.append(
                f"[{i}:a]adelay={delay_ms}|{delay_ms},volume={volume}[v{i}];"
            )
        
        # If there's original audio that needs ducking
        duck_nodes = []
        for i, mix in enumerate(self.mix_inputs, 1):
            if not mix['lyrics_mode']:
                start_ms = int(mix['start'] * 1000)
                duration_ms = int(mix['duration'] * 1000)
                
                # Create volume ducking curve for original audio during this segment
                duck_node = f"[orig]volume=enable='between(t,{mix['start']},{mix['start']+mix['duration']})':volume=0.2[duck{i}];"
                filter_complex.append(duck_node)
                duck_nodes.append(f"[duck{i}]")
        
        # Mix all streams together
        mix_line = f"{','.join(duck_nodes + [f'[v{i}]' for i in range(1, input_count)])}"
        filter_complex.append(f"{mix_line}amix=inputs={len(duck_nodes) + len(self.mix_inputs)}:normalize=0[out]")
        
        # Build FFmpeg command
        output_path = self.temp_dir / "final_audio.ac3"
        cmd = ['ffmpeg', '-y']
        
        # Add input files
        cmd.extend(['-i', str(self.orig_audio)])
        for mix in self.mix_inputs:
            cmd.extend(['-i', str(mix['file'])])
        
        # Add filter complex
        cmd.extend([
            '-filter_complex', ''.join(filter_complex),
            '-map', '[out]',
            '-c:a', 'ac3',
            '-b:a', '192k',
            str(output_path)
        ])
        
        # Run final mix
        print("Running FFmpeg mix...")
        print(f"Filter graph: {''.join(filter_complex)}")
        subprocess.run(cmd, check=True)
        
        print(f"Final audio mixing took {time.time() - start_time:.2f} seconds")
        return output_path

    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir) 