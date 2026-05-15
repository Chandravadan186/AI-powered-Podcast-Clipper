import json
import os
import time
import subprocess
import google.generativeai as genai
from faster_whisper import WhisperModel
import torch
import whisper



class LocalAiPodcastClipper:
    def __init__(self):
        self._models_loaded = False
        self.whisper_model = None
        self.gemini_model = None

    def ensure_models_loaded(self):
        if self._models_loaded:
            return
        try:
            # Automatically fallback to CPU if CUDA is not available
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            if device == "cuda":
                print("Transcription running on GPU")
            else:
                print("Transcription running on CPU")
            
            # Replaced Whisper with Faster-Whisper (Safe Windows Initialization)
            self.whisper_model = WhisperModel(
                "base",
                device=device,
                compute_type="float16" if device == "cuda" else "int8"
            )

            print("Configuring Gemini SDK...")
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                print("Warning: GEMINI_API_KEY not found in environment")
            genai.configure(api_key=api_key)
            
            # Detect available models and select the best one
            print("Detecting available Gemini models...")
            available_models = []
            try:
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        available_models.append(m.name)
                print(f"Available Gemini models: {available_models}")
            except Exception as e:
                print(f"Error listing Gemini models: {e}")
                available_models = ["models/gemini-flash-latest", "models/gemini-1.5-flash", "models/gemini-1.5-pro"] # Fallback list

            # Selection priority
            priority_order = [
                "models/gemini-flash-latest",
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro",
                "models/gemini-pro-latest",
                "models/gemini-pro",
                "models/gemini-1.0-pro"
            ]
            
            selected_model = None
            for model_name in priority_order:
                if any(model_name in am for am in available_models):
                    selected_model = model_name
                    break
            
            if not selected_model:
                selected_model = "models/gemini-1.5-flash" # Absolute fallback
                
            print(f"Selected Gemini model: {selected_model}")
            self.gemini_model = genai.GenerativeModel(selected_model)
            
            self._models_loaded = True
            print("Local models loaded successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to load local models: {e}")

    def transcribe_video(self, base_dir, video_path):
        self.ensure_models_loaded()

        audio_path = base_dir / "audio.wav"
        extract_cmd = (
            f"ffmpeg -y -i \"{video_path}\" -vn -acodec pcm_s16le -ar 16000 -ac 1 \"{audio_path}\""
        )
        subprocess.run(extract_cmd, shell=True, check=True, capture_output=True)

        start_time = time.time()
        # Starting transcription
        print("Starting transcription...")
        # Faster-Whisper transcribe with VAD filter to skip silence
        fw_segments, info = self.whisper_model.transcribe(
            str(audio_path),
            vad_filter=True
        )
        
        # Convert Faster-Whisper segments to the list format expected by downstream logic
        segments = []
        for fw_seg in fw_segments:
            # Each fw_seg has .start, .end, and .text
            text = fw_seg.text.strip()
            if not text:
                continue
                
            words = text.split()
            if not words:
                continue
                
            seg_start = fw_seg.start
            seg_end = fw_seg.end
            seg_duration = seg_end - seg_start
            word_duration = seg_duration / len(words)
            
            current_time = seg_start
            for word in words:
                segments.append({
                    "start": current_time,
                    "end": current_time + word_duration,
                    "word": word
                })
                current_time += word_duration
        
        # Transcription finished
        print("Transcription finished.")
        duration = time.time() - start_time
        print(f"Transcription took {duration:.2f} seconds")

        return json.dumps(segments)

    def score_segment(self, segment_text: str):
        """Score a transcript segment based on viral potential (1-100)."""
        self.ensure_models_loaded()
        
        prompt = f"""
    You are an expert viral content strategist.
    
    Analyze the following podcast transcript segment and determine its viral potential for short-form platforms like TikTok, YouTube Shorts, and Instagram Reels.
    
    Evaluate based on:
    
    * emotional intensity
    * controversial or surprising statements
    * storytelling
    * strong opinions
    * relatable advice
    * curiosity factor
    
    Transcript Segment:
    {segment_text}
    
    Return ONLY JSON:
    
    {{
    "score": 0-100,
    "hook": "first sentence that would hook viewers",
    "category": "motivation | story | controversy | insight | advice",
    "reason": "short explanation"
    }}
    """
        print("Gemini scoring segment...")
        try:
            response = self.gemini_model.generate_content(prompt)
            print("Gemini response:", response.text)
            
            # Robust extraction of text
            if not response.candidates:
                print("Warning: Gemini returned no candidates (blocked or empty).")
                return {"score": 50, "hook": "", "category": "insight", "reason": "No response candidates"}

            cleaned = response.text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[len("```json"):].strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-len("```")].strip()
            
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                # Try to extract JSON from the string if there's preamble
                import re
                match = re.search(r"\{.*\}", cleaned, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                raise
                
        except Exception as e:
            print("Gemini scoring error:", e)
            # Fallback for failed scoring
            return {"score": 50, "hook": "", "category": "insight", "reason": f"Error: {str(e)}"}

    def identify_moments(self, transcript_segments, clipType="short"):
        self.ensure_models_loaded()
        
        # Adjust prompt based on clipType
        if clipType == "short":
            prompt_duration = "between 30 and 60 seconds long. Each clip should never exceed 60 seconds. Find 4–6 viral moments."
            format_instruction = 'Format the output as a list of JSON objects: {"clips": [{"start": seconds, "end": seconds}, ...]}'
        elif clipType == "long":
            prompt_duration = "between 4 and 6 minutes long. Find 1–2 meaningful segments."
            format_instruction = 'Format the output as a list of JSON objects: {"clips": [{"start": seconds, "end": seconds}, ...]}'
        else: # "both"
            prompt_duration = "both short viral moments (30-60s) and long meaningful segments (4-6m)."
            format_instruction = 'Format the output as a JSON object: {"short_clips": [{"start": seconds, "end": seconds}, ...], "long_clips": [{"start": seconds, "end": seconds}, ...]}'

        contents = f"""
    This is a podcast video transcript consisting of word, along with each words's start and end time. 
    I am looking to create clips that are {prompt_duration}.

    Your task is to find and extract stories, or question and their corresponding answers from the transcript.
    Each clip should begin with the question and conclude with the answer.
    It is acceptable for the clip to include a few additional sentences before a question if it aids in contextualizing the question.

    Please adhere to the following rules:
    - Ensure that clips do not overlap with one another.
    - Start and end timestamps of the clips should align perfectly with the sentence boundaries in the transcript.
    - Only use the start and end timestamps provided in the input. Modifying timestamps is not allowed.
    - {format_instruction}
    - The output should always be readable by the python json.loads function.

    Avoid including:
    - Moments of greeting, thanking, or saying goodbye.
    - Non-question and answer interactions.

    If there are no valid clips to extract, the output should be an empty list or object as specified above, in JSON format. Also readable by json.loads() in Python.

    The transcript is as follows:\n\n{str(transcript_segments)}
    """

        print("Gemini identifying moments...")
        try:
            response = self.gemini_model.generate_content(contents)
            print("Gemini response:", response)
            
            if not response.candidates:
                print("Warning: Gemini returned no candidates for identify_moments.")
                return "[]"
                
            return response.text
        except Exception as e:
            print(f"Error identifying moments with Gemini: {e}")
            return "[]"

