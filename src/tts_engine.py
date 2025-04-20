from pathlib import Path
import tempfile
from gtts import gTTS
import subprocess
import time
import os
import uuid

class TTSEngine:
    def __init__(self, language: str = 'et'):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.language = language
        
    def generate_speech(self, text: str, speed: float = 1.0) -> Path:
        """Generate speech with a unique filename to avoid conflicts in parallel processing"""
        print(f"Generating speech for: '{text}' with speed={speed}")
        start_time = time.time()
        
        # Use UUID to ensure unique filenames across processes
        unique_id = uuid.uuid4()
        mp3_path = self.temp_dir / f"{unique_id}.mp3"
        wav_path = self.temp_dir / f"{unique_id}.wav"
        
        try:
            # Generate MP3
            tts = gTTS(text=text, lang=self.language, slow=False)
            tts.save(str(mp3_path))
            print(f"MP3 generation took {time.time() - start_time:.2f} seconds")
            
            # Convert to WAV with speed adjustment
            cmd = ['ffmpeg', '-i', str(mp3_path)]
            if speed != 1.0:
                cmd += ['-filter:a', f'atempo={speed}']
            cmd += [
                '-acodec', 'pcm_s16le',
                '-ar', '48000',
                '-ac', '2',
                '-y',
                str(wav_path)
            ]
            
            ffmpeg_start = time.time()
            subprocess.run(cmd, capture_output=True, check=True, timeout=30)
            print(f"FFmpeg conversion took {time.time() - ffmpeg_start:.2f} seconds")
            
            if wav_path.stat().st_size < 1000:
                raise RuntimeError("Generated WAV file is too small")
            
            mp3_path.unlink()
            return wav_path
            
        except Exception as e:
            if mp3_path.exists():
                mp3_path.unlink()
            if wav_path.exists():
                wav_path.unlink()
            raise e
    
    def cleanup(self):
        import shutil
        shutil.rmtree(self.temp_dir) 