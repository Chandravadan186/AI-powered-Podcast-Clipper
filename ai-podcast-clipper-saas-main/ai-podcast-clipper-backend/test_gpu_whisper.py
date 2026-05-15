import torch
from faster_whisper import WhisperModel

def run_diagnostic():
    print("--- Faster-Whisper GPU Diagnostic ---")
    
    # Step 1 — Check PyTorch GPU availability
    cuda_available = torch.cuda.is_available()
    print(f"CUDA available: {cuda_available}")
    
    if cuda_available:
        print(f"GPU Name: {torch.cuda.get_device_name(0)}")
    
    # Step 2 — Detect device automatically
    device = "cuda" if cuda_available else "cpu"
    print(f"Device selected: {device}")
    
    # Step 3 — Load Faster-Whisper model
    print(f"Initializing Faster-Whisper (tiny) on {device}...")
    try:
        model = WhisperModel(
            "tiny",
            device=device,
            compute_type="float16" if device == "cuda" else "int8"
        )
        
        # Step 4 — Print confirmation
        print("Faster-Whisper initialized successfully")
        
        # Step 5 — Show whether GPU or CPU is used
        if device == "cuda":
            print("Running on GPU (CUDA)")
        else:
            print("Running on CPU")
            
    except Exception as e:
        print(f"Error initializing Faster-Whisper: {e}")

if __name__ == "__main__":
    run_diagnostic()
