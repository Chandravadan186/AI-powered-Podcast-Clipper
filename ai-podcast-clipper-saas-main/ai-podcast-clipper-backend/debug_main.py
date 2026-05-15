
import sys
from unittest.mock import MagicMock

# Mock modules that might be missing or heavy
sys.modules["modal"] = MagicMock()
sys.modules["ffmpegcv"] = MagicMock()
sys.modules["whisperx"] = MagicMock()
sys.modules["boto3"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["pysubs2"] = MagicMock()
sys.modules["numpy"] = MagicMock()

# Mock modal.App and Image to behave reasonably
mock_app_instance = MagicMock()
sys.modules["modal"].App.return_value = mock_app_instance
sys.modules["modal"].Image.from_registry.return_value.apt_install.return_value.pip_install_from_requirements.return_value.run_commands.return_value.add_local_dir.return_value = MagicMock()

# Mock FastAPI
sys.modules["fastapi"] = MagicMock()
sys.modules["fastapi.middleware"] = MagicMock()
sys.modules["fastapi.middleware.cors"] = MagicMock()
sys.modules["fastapi.security"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()
sys.modules["pydantic"] = MagicMock()

import os
# Ensure USE_MODAL is 0
os.environ["USE_MODAL"] = "0"

print("Attempting to import main...")
try:
    import main
    print("Import successful.")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)

print("Checking for 'app' in main...")
if hasattr(main, "app"):
    print(f"Found 'app': {main.app}")
else:
    print("ERROR: 'app' NOT found in main module.")

print("Checking for 'fastapi_app' in main...")
if hasattr(main, "fastapi_app"):
    print(f"Found 'fastapi_app': {main.fastapi_app}")
else:
    print("'fastapi_app' NOT found.")
