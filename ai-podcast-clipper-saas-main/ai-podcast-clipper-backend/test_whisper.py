import sys
from faster_whisper import WhisperModel
import torch

def test_whisper_startup():
    print("Testing Faster-Whisper startup...")
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Device detected: {device}")
        
        # Load a tiny model for fast testing
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("Faster-Whisper model (tiny) loaded successfully on CPU!")
        
        if device == "cuda":
            print("Attempting to load on GPU...")
            gpu_model = WhisperModel("tiny", device="cuda", compute_type="float16")
            print("Faster-Whisper model (tiny) loaded successfully on GPU!")
            
        print("\nSUCCESS: Faster-Whisper environment is correctly configured.")
        return True
    except Exception as e:
        print(f"\nFAILURE: Faster-Whisper failed to load: {e}")
        return False

if __name__ == "__main__":
    test_whisper_startup()
