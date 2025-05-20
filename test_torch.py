import sys
import subprocess
import pkg_resources

print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print("\nInstalled packages:")

installed_packages = pkg_resources.working_set
installed_packages_list = sorted([f"{package.key} {package.version}" for package in installed_packages])
for package in installed_packages_list:
    print(package)

print("\nAttempting to import torch:")
try:
    import torch
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
except ImportError as e:
    print(f"Error importing torch: {e}")

print("\nAttempting to import TTS:")
try:
    from TTS.api import TTS
    print("TTS import successful")
except ImportError as e:
    print(f"Error importing TTS: {e}")
except Exception as e:
    print(f"Other error with TTS: {e}") 