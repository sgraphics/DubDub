import sys
from pathlib import Path
from media_processor import MediaProcessor
from subtitle_processor import SubtitleProcessor, SubtitleEntry
from audio_mixer import AudioMixer
from tts_engine import TTSEngine
import re
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Tuple
from tqdm import tqdm  # For progress bar
import tempfile

class AIDubber:
    def __init__(self):
        self.media_processor = MediaProcessor()
        self.subtitle_processor = SubtitleProcessor()
        self.audio_mixer = AudioMixer()
        self.tts_engine = TTSEngine()
        # Add temporary directory
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def process_subtitle_chunk(self, chunk: List[SubtitleEntry], video_path: Path, temp_dir: Path) -> List[Tuple[float, Path, float, float, bool]]:
        """Process a chunk of subtitles and return timing/audio data"""
        results = []
        for subtitle in chunk:
            try:
                # Check if it's lyrics (has HTML tags)
                is_lyrics = '<i>' in subtitle.text.lower() or '</i>' in subtitle.text.lower()
                
                # Generate TTS audio
                clean_text = re.sub(r'<[^>]*>', '', subtitle.text)
                tts_audio = self.tts_engine.generate_speech(clean_text, speed=1.25)
                
                # Return tuple of (start_time, audio_path, duration, end_time, is_lyrics)
                results.append((
                    subtitle.start_time,
                    tts_audio,
                    subtitle.end_time - subtitle.start_time,
                    subtitle.end_time,
                    is_lyrics
                ))
            except Exception as e:
                print(f"Error processing subtitle: {str(e)}")
                continue
        return results

    def process_file(self, video_path: str, subtitle_path: str, output_path: str):
        try:
            # Load the video file
            video = self.media_processor.load_video(video_path)
            
            # Parse subtitles
            subtitles = self.subtitle_processor.parse_srt(subtitle_path)
            
            # Calculate chunks based on CPU cores
            num_cores = multiprocessing.cpu_count()
            chunk_size = max(1, len(subtitles) // num_cores)
            subtitle_chunks = [subtitles[i:i + chunk_size] for i in range(0, len(subtitles), chunk_size)]
            
            # Process chunks in parallel
            all_results = []
            with ProcessPoolExecutor(max_workers=num_cores) as executor:
                # Submit all chunks for processing
                future_to_chunk = {
                    executor.submit(
                        self.process_subtitle_chunk, 
                        chunk, 
                        Path(video_path),
                        self.temp_dir
                    ): i for i, chunk in enumerate(subtitle_chunks)
                }
                
                # Collect results as they complete
                for future in tqdm(as_completed(future_to_chunk), total=len(subtitle_chunks), desc="Processing subtitle chunks"):
                    chunk_results = future.result()
                    all_results.extend(chunk_results)
            
            # Sort results by start time
            all_results.sort(key=lambda x: x[0])
            
            # Mix audio sequentially (can't parallelize this part easily)
            last_end_time = 0.0
            for start_time, tts_audio, duration, end_time, is_lyrics in tqdm(all_results, desc="Mixing audio"):
                actual_start = max(last_end_time, start_time)
                tts_length_secs = self.audio_mixer.mix_audio_segment(
                    video,
                    tts_audio,
                    actual_start,
                    duck_level=0.2,
                    lyrics_mode=is_lyrics
                )
                last_end_time = actual_start + tts_length_secs
            
            # Save the final mixed audio
            final_audio = self.audio_mixer.save_final_audio()
            self.media_processor.save_video(video, final_audio, output_path)
            
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        
        try:
            self.tts_engine.cleanup()
        except Exception as e:
            print(f"Note: TTS engine cleanup had an issue: {e}")
        
        try:
            self.audio_mixer.cleanup()
        except Exception as e:
            print(f"Note: Audio mixer cleanup had an issue: {e}")
        
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Note: Temporary directory cleanup had an issue: {e}")

def main():
    if len(sys.argv) != 4:
        print("Usage: python main.py <video_path> <subtitle_path> <output_path>")
        return
    
    dubber = AIDubber()
    dubber.process_file(sys.argv[1], sys.argv[2], sys.argv[3])

if __name__ == "__main__":
    main() 