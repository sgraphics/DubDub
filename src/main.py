import sys
import os
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
import hashlib
import time
import traceback

class AIDubber:
    def __init__(self, language: str = 'et'):
        self.media_processor = MediaProcessor()
        self.subtitle_processor = SubtitleProcessor()
        self.audio_mixer = AudioMixer()
        self.tts_engine = TTSEngine(language)
        self.language = language
        
        # Create temp directory with a short path to avoid Windows path length limitations
        temp_base = os.environ.get('TEMP', tempfile.gettempdir())
        short_dir_name = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self.temp_dir = Path(temp_base) / short_dir_name
        self.temp_dir.mkdir(exist_ok=True)
        
        print(f"Temporary directory: {self.temp_dir}")
        print(f"Using language: {language}")
    
    def process_subtitle_chunk(self, chunk: List[SubtitleEntry], video_path: Path, temp_dir: Path) -> List[Tuple[float, Path, float, float, bool]]:
        """Process a chunk of subtitles and return timing/audio data"""
        results = []
        for subtitle in chunk:
            try:
                # Check if it's lyrics (has HTML tags)
                is_lyrics = '<i>' in subtitle.text.lower() or '</i>' in subtitle.text.lower()
                
                # Clean the text - only remove HTML tags and quotation marks
                clean_text = re.sub(r'<[^>]*>', '', subtitle.text)  # Remove HTML tags
                clean_text = re.sub(r'["""„]', '', clean_text)  # Remove various quote marks
                clean_text = clean_text.strip()  # Just trim whitespace
                
                # Generate TTS audio
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
            # Validate paths and create full paths
            video_path = os.path.abspath(video_path)
            # Check if subtitle_path is a file path or a language code
            is_language_code = not ('/' in subtitle_path or '\\' in subtitle_path or '.' in subtitle_path)
            
            if is_language_code:
                print(f"Subtitle path '{subtitle_path}' appears to be a language code. Attempting to extract subtitles from video.")
                language_code = subtitle_path
                video_path_obj = Path(video_path)
                
                # Load the video file
                video = self.media_processor.load_video(video_path)
                
                # Extract subtitles from the video file
                extracted_subtitle_path, available_languages = self.media_processor.extract_subtitles(video, language_code)
                
                if extracted_subtitle_path is None:
                    if available_languages:
                        available_langs_str = ", ".join(available_languages)
                        raise RuntimeError(f"Could not extract subtitles with language code '{language_code}' from the video file. Available subtitle languages: {available_langs_str}")
                    else:
                        raise RuntimeError(f"Could not extract subtitles with language code '{language_code}' from the video file. No subtitle tracks found.")
                
                subtitle_path = str(extracted_subtitle_path)
            else:
                subtitle_path = os.path.abspath(subtitle_path)
                # Load the video file
                video = self.media_processor.load_video(video_path)
            
            output_path = os.path.abspath(output_path)
            
            print(f"Processing video: {video_path}")
            print(f"Using subtitles: {subtitle_path}")
            print(f"Output will be saved to: {output_path}")
            
            # Check if paths are too long for Windows (260 char limit)
            for path, name in [(video_path, "Video"), (subtitle_path, "Subtitle"), (output_path, "Output")]:
                if len(str(path)) > 240:
                    print(f"Warning: {name} path is very long ({len(str(path))} chars)")
                    print(f"  {path}")
            
            # Parse subtitles
            subtitles = self.subtitle_processor.parse_srt(subtitle_path)
            print(f"Found {len(subtitles)} subtitle entries")
            
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
            print(f"Generated speech for {len(all_results)} subtitle entries")
            
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
            print("Creating final mixed audio track...")
            final_audio = self.audio_mixer.save_final_audio()
            
            # Save the final video with language metadata
            print(f"Creating final output file: {output_path}")
            self.media_processor.save_video(video, final_audio, output_path, language=self.language)
            
            print(f"\nSuccess! Output saved to: {output_path}")
            
        except Exception as e:
            print(f"\nError during processing: {str(e)}")
            traceback.print_exc()
            raise
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        
        print("Cleaning up temporary files...")
        
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
    import argparse
    parser = argparse.ArgumentParser(description='AI Video Dubbing Tool')
    parser.add_argument('video_path', help='Path to the input video file')
    parser.add_argument('subtitle_path', help='Path to the subtitle file (.srt format) or language code to extract from the video')
    parser.add_argument('output_path', help='Path where the dubbed video will be saved')
    parser.add_argument('--language', '-l', default='et', help='Language code for TTS (default: et)')
    
    args = parser.parse_args()
    
    try:
        dubber = AIDubber(language=args.language)
        dubber.process_file(args.video_path, args.subtitle_path, args.output_path)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 