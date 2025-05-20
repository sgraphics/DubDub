import os
import sys
import traceback

try:
    import torch
    from TTS.api import TTS

    # Print diagnostic information
    print(f"Python version: {sys.version}")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    if torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        device = "cuda"
    else:
        print("CUDA not available, using CPU")
        device = "cpu"
    
    # List available models
    print("\nListing available TTS models...")
    tts = TTS()
    models = tts.list_models()
    
    # Look for Estonian models
    estonian_models = [model for model in models if "/est/" in model]
    print("\nAvailable Estonian models:")
    for model in estonian_models:
        print(f"- {model}")
    
    if not estonian_models:
        print("No Estonian models found. Available models:")
        for model in models[:10]:  # Just show first 10 to avoid overwhelming output
            print(f"- {model}")
        print(f"... and {len(models) - 10} more")
    
    # Try to initialize the Estonian TTS model
    model_name = "tts_models/est/fairseq/vits"
    print(f"\nInitializing model: {model_name}")
    tts = TTS(model_name=model_name).to(device)
    
    # Estonian text sample
    estonian_text = "Tere, kuidas sul läheb? Hästi! Mis on elu? \"Hästi\", ütles ta."
    
    # Generate speech and save to file
    output_file = "estonian_speech.wav"
    print(f"Generating speech for text: '{estonian_text}'")
    tts.tts_to_file(text=estonian_text, file_path=output_file)
    
    print(f"Success! Speech generated and saved to {output_file}")

except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please install the required packages with: pip install torch TTS")
except Exception as e:
    print(f"Error: {e}")
    print(traceback.format_exc()) 