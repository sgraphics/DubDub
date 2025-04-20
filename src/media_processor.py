import subprocess
from pathlib import Path
import tempfile
import shutil
from typing import List

class MediaProcessor:
    def __init__(self):
        # Default MKVToolNix installation path
        self.mkvmerge = r"C:\Program Files\MKVToolNix\mkvmerge.exe"
        self._verify_mkvtoolnix()
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def _verify_mkvtoolnix(self):
        try:
            result = subprocess.run([self.mkvmerge, '--version'], capture_output=True, text=True)
            print(f"MKVMerge version: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            raise RuntimeError(f"MKVToolNix not found at {self.mkvmerge}. Please install MKVToolNix first.")

    def load_video(self, video_path: str) -> Path:
        # Copy video to temp directory
        video_path = Path(video_path)
        temp_video = self.temp_dir / video_path.name
        shutil.copy2(video_path, temp_video)
        return temp_video

    def save_video(self, video_path: Path, dubbed_audio: Path, output_path: str):
        """
        Merge video with the dubbed audio track while preserving original audio
        """
        print("\nMerging final video...")
        print(f"Video: {video_path}")
        print(f"Dubbed audio: {dubbed_audio}")
        print(f"Output: {output_path}")
        
        # Use mkvmerge to add the dubbed audio track and set it as default
        cmd = [
            self.mkvmerge,
            '-o', output_path,
            # Video file with all streams
            str(video_path),
            # Add dubbed audio track
            '--track-name', '0:AI Dubbed Audio (Estonian)',
            '--language', '0:et',
            '--default-track', '0:yes',  # Set the new audio track as default
            str(dubbed_audio)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            print("\nMKVMerge output:")
            print(result.stdout)
            if result.stderr:
                print("\nMKVMerge errors:")
                print(result.stderr)
            
            if result.returncode != 0:
                raise RuntimeError(f"MKVMerge failed with return code {result.returncode}")
                
            if not Path(output_path).exists():
                raise RuntimeError("Output file was not created")
                
        except Exception as e:
            print(f"\nError during video merge: {str(e)}")
            raise

    def cleanup(self):
        shutil.rmtree(self.temp_dir)

    # Alternative method for quick testing
    def quick_test_merge(self, video_path: str, aac_audio_path: str, output_path: str):
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