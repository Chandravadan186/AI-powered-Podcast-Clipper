import torch
from faster_whisper import WhisperModel

def test_device():
    # Step 1 — Detect CUDA availability
    cuda_available = torch.cuda.is_available()
    print(f"CUDA available: {cuda_available}")

    # Step 2 — Print GPU name if available
    if cuda_available:
        print(f"GPU Name: {torch.cuda.get_device_name(0)}")

    # Step 3 — Detect device automatically
    device = "cuda" if cuda_available else "cpu"
    print(f"Device selected: {device}")

    # Step 4 — Initialize Faster-Whisper using the exact same configuration used in the backend
    print(f"Initializing Faster-Whisper (base) on {device}...")
    try:
        model = WhisperModel(
            "base",
            device=device,
            compute_type="float16" if device == "cuda" else "int8"
        )

        # Step 5 — Print confirmation
        print("Faster-Whisper initialized successfully")

        # Step 6 — Show which mode is running
        if device == "cuda":
            print("Transcription will run on GPU")
        else:
            print("Transcription will run on CPU")
            
    except Exception as e:
        print(f"Error initializing Faster-Whisper: {e}")

if __name__ == "__main__":
    test_device()
