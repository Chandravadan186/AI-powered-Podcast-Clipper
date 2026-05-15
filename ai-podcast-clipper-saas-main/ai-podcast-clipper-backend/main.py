import glob
import json
import pathlib
import pickle
import random
import shutil
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
# import boto3
import cv2
import tempfile
from fastapi import Depends, HTTPException, status, FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
try:
    import ffmpegcv
except RuntimeError:
    print("Warning: ffmpegcv could not be imported (likely missing ffmpeg). Local video processing will fail.")
    ffmpegcv = None
import modal
import numpy as np
from pydantic import BaseModel
import os
import google.generativeai as genai
import uvicorn
import supabase_storage

import pysubs2
from tqdm import tqdm
from faster_whisper import WhisperModel
import torch
import whisper


class ProcessVideoRequest(BaseModel):
    s3_key: str


image = (modal.Image.from_registry(
    "nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.12")
    .apt_install(["ffmpeg", "libgl1-mesa-glx", "wget", "libcudnn8", "libcudnn8-dev"])
    .pip_install_from_requirements("requirements.txt")
    .run_commands(["mkdir -p /usr/share/fonts/truetype/custom",
                   "wget -O /usr/share/fonts/truetype/custom/Anton-Regular.ttf https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
                   "fc-cache -f -v"])
    .add_local_dir("asd", "/asd", copy=True))

app = modal.App("ai-podcast-clipper", image=image)

volume = modal.Volume.from_name(
    "ai-podcast-clipper-model-cache", create_if_missing=True
)

mount_path = "/root/.cache/torch"

auth_scheme = HTTPBearer()


def create_vertical_video(tracks, scores, pyframes_path, pyavi_path, audio_path, output_path, framerate=25):
    target_width = 1080
    target_height = 1920

    flist = glob.glob(os.path.join(pyframes_path, "*.jpg"))
    flist.sort()

    faces = [[] for _ in range(len(flist))]

    for tidx, track in enumerate(tracks):
        score_array = scores[tidx]
        for fidx, frame in enumerate(track["track"]["frame"].tolist()):
            slice_start = max(fidx - 30, 0)
            slice_end = min(fidx + 30, len(score_array))
            score_slice = score_array[slice_start:slice_end]
            avg_score = float(np.mean(score_slice)
                              if len(score_slice) > 0 else 0)

            faces[frame].append(
                {'track': tidx, 'score': avg_score, 's': track['proc_track']["s"][fidx], 'x': track['proc_track']["x"][fidx], 'y': track['proc_track']["y"][fidx]})

    temp_video_path = os.path.join(pyavi_path, "video_only.mp4")

    vout = None
    for fidx, fname in tqdm(enumerate(flist), total=len(flist), desc="Creating vertical video"):
        img = cv2.imread(fname)
        if img is None:
            continue

        current_faces = faces[fidx]

        max_score_face = max(
            current_faces, key=lambda face: face['score']) if current_faces else None

        if max_score_face and max_score_face['score'] < 0:
            max_score_face = None

        if vout is None:
            vout = ffmpegcv.VideoWriterNV(
                file=temp_video_path,
                codec=None,
                fps=framerate,
                resize=(target_width, target_height)
            )

        if max_score_face:
            mode = "crop"
        else:
            mode = "resize"

        if mode == "resize":
            scale = target_width / img.shape[1]
            resized_height = int(img.shape[0] * scale)
            resized_image = cv2.resize(
                img, (target_width, resized_height), interpolation=cv2.INTER_AREA)

            scale_for_bg = max(
                target_width / img.shape[1], target_height / img.shape[0])
            bg_width = int(img.shape[1] * scale_for_bg)
            bg_heigth = int(img.shape[0] * scale_for_bg)

            blurred_background = cv2.resize(img, (bg_width, bg_heigth))
            blurred_background = cv2.GaussianBlur(
                blurred_background, (121, 121), 0)

            crop_x = (bg_width - target_width) // 2
            crop_y = (bg_heigth - target_height) // 2
            blurred_background = blurred_background[crop_y:crop_y +
                                                    target_height, crop_x:crop_x + target_width]

            center_y = (target_height - resized_height) // 2
            blurred_background[center_y:center_y +
                               resized_height, :] = resized_image

            vout.write(blurred_background)

        elif mode == "crop":
            scale = target_height / img.shape[0]
            resized_image = cv2.resize(
                img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            frame_width = resized_image.shape[1]

            center_x = int(
                max_score_face["x"] * scale if max_score_face else frame_width // 2)
            top_x = max(min(center_x - target_width // 2,
                        frame_width - target_width), 0)

            image_cropped = resized_image[0:target_height,
                                          top_x:top_x + target_width]

            vout.write(image_cropped)

    if vout:
        vout.release()

    ffmpeg_command = (f"ffmpeg -y -i \"{temp_video_path}\" -i \"{audio_path}\" "
                      f"-c:v h264 -preset fast -crf 23 -c:a aac -b:a 128k "
                      f"\"{output_path}\"")
    subprocess.run(ffmpeg_command, shell=True, check=True, text=True)


def create_subtitles_with_ffmpeg(transcript_segments: list, clip_start: float, clip_end: float, clip_video_path: str, output_path: str, max_words: int = 5):
    temp_dir = os.path.dirname(output_path)
    subtitle_path = os.path.join(temp_dir, "temp_subtitles.ass")

    clip_segments = [segment for segment in transcript_segments
                     if segment.get("start") is not None
                     and segment.get("end") is not None
                     and segment.get("end") > clip_start
                     and segment.get("start") < clip_end
                     ]

    subtitles = []
    current_words = []
    current_start = None
    current_end = None

    for segment in clip_segments:
        word = segment.get("word", "").strip()
        seg_start = segment.get("start")
        seg_end = segment.get("end")

        if not word or seg_start is None or seg_end is None:
            continue

        start_rel = max(0.0, seg_start - clip_start)
        end_rel = max(0.0, seg_end - clip_start)

        if end_rel <= 0:
            continue

        if not current_words:
            current_start = start_rel
            current_end = end_rel
            current_words = [word]
        elif len(current_words) >= max_words:
            subtitles.append(
                (current_start, current_end, ' '.join(current_words)))
            current_words = [word]
            current_start = start_rel
            current_end = end_rel
        else:
            current_words.append(word)
            current_end = end_rel

    if current_words:
        subtitles.append(
            (current_start, current_end, ' '.join(current_words)))

    subs = pysubs2.SSAFile()

    subs.info["WrapStyle"] = 0
    subs.info["ScaledBorderAndShadow"] = "yes"
    subs.info["PlayResX"] = 1080
    subs.info["PlayResY"] = 1920
    subs.info["ScriptType"] = "v4.00+"

    style_name = "Default"
    new_style = pysubs2.SSAStyle()
    new_style.fontname = "Anton"
    new_style.fontsize = 140
    new_style.primarycolor = pysubs2.Color(255, 255, 255)
    new_style.outline = 2.0
    new_style.shadow = 2.0
    new_style.shadowcolor = pysubs2.Color(0, 0, 0, 128)
    new_style.alignment = 2
    new_style.marginl = 50
    new_style.marginr = 50
    new_style.marginv = 50
    new_style.spacing = 0.0

    subs.styles[style_name] = new_style

    for i, (start, end, text) in enumerate(subtitles):
        start_time = pysubs2.make_time(s=start)
        end_time = pysubs2.make_time(s=end)
        line = pysubs2.SSAEvent(
            start=start_time, end=end_time, text=text, style=style_name)
        subs.events.append(line)

    subs.save(subtitle_path)

    # Ensure subtitle path is safe for ffmpeg filter (forward slashes, escaped colons if needed)
    # ffmpeg on Windows can handle forward slashes in paths
    safe_subtitle_path = subtitle_path.replace('\\', '/')
    # For filter complex, we need to escape the colon in drive letter, e.g. C:/ -> C\:/
    safe_subtitle_path = safe_subtitle_path.replace(':', '\\:')

    ffmpeg_cmd = (f"ffmpeg -y -i \"{clip_video_path}\" -vf \"ass='{safe_subtitle_path}'\" "
                  f"-c:v h264 -preset fast -crf 23 \"{output_path}\"")

    subprocess.run(ffmpeg_cmd, shell=True, check=True)


def process_clip(base_dir: str, original_video_path: str, s3_key: str, start_time: float, end_time: float, clip_index: int, transcript_segments: list):
    clip_name = f"clip_{clip_index}"
    s3_key_dir = os.path.dirname(s3_key)
    output_s3_key = f"{s3_key_dir}/short/{clip_name}.mp4"
    print(f"Output Storage key: {output_s3_key}")

    clip_dir = base_dir / clip_name
    clip_dir.mkdir(parents=True, exist_ok=True)

    clip_segment_path = clip_dir / f"{clip_name}_segment.mp4"
    vertical_mp4_path = clip_dir / "pyavi" / "video_out_vertical.mp4"
    subtitle_output_path = clip_dir / "pyavi" / "video_with_subtitles.mp4"

    (clip_dir / "pywork").mkdir(exist_ok=True)
    pyframes_path = clip_dir / "pyframes"
    pyavi_path = clip_dir / "pyavi"
    audio_path = clip_dir / "pyavi" / "audio.wav"

    pyframes_path.mkdir(exist_ok=True)
    pyavi_path.mkdir(exist_ok=True)

    duration = end_time - start_time
    cut_command = (f"ffmpeg -y -i \"{original_video_path}\" -ss {start_time} -t {duration} "
                   f"\"{clip_segment_path}\"")
    subprocess.run(cut_command, shell=True, check=True,
                   capture_output=True, text=True)

    extract_cmd = f"ffmpeg -y -i \"{clip_segment_path}\" -vn -acodec pcm_s16le -ar 16000 -ac 1 \"{audio_path}\""
    subprocess.run(extract_cmd, shell=True,
                   check=True, capture_output=True)

    shutil.copy(clip_segment_path, base_dir / f"{clip_name}.mp4")

    columbia_command = (f"python Columbia_test.py --videoName {clip_name} "
                        f"--videoFolder {str(base_dir)} "
                        f"--pretrainModel weight/finetuning_TalkSet.model")

    columbia_start_time = time.time()
    
    # Determine correct cwd for ASD script
    asd_cwd = "/asd"
    if not os.path.exists(asd_cwd):
        # Fallback for local execution
        possible_asd = pathlib.Path(__file__).parent / "asd"
        if possible_asd.exists():
            asd_cwd = str(possible_asd)
        else:
             print(f"Warning: ASD directory not found at {possible_asd} or /asd. Active Speaker Detection may fail.")
    
    subprocess.run(columbia_command, cwd=asd_cwd, shell=True)
    columbia_end_time = time.time()
    print(
        f"Columbia script completed in {columbia_end_time - columbia_start_time:.2f} seconds")

    tracks_path = clip_dir / "pywork" / "tracks.pckl"
    scores_path = clip_dir / "pywork" / "scores.pckl"
    
    if not tracks_path.exists() or not scores_path.exists():
        print("Warning: Tracks or scores not found (ASD failed or missing). Falling back to center crop.")
        # Create a simple center crop vertical video to allow pipeline to continue
        # Assuming 16:9 input, crop to 9:16 center
        fallback_cmd = (f"ffmpeg -y -i \"{clip_segment_path}\" -vf \"crop=ih*(9/16):ih\" "
                        f"-c:a copy \"{vertical_mp4_path}\"")
        subprocess.run(fallback_cmd, shell=True, check=True)
    else:
        with open(tracks_path, "rb") as f:
            tracks = pickle.load(f)

        with open(scores_path, "rb") as f:
            scores = pickle.load(f)

        cvv_start_time = time.time()
        create_vertical_video(
            tracks, scores, pyframes_path, pyavi_path, audio_path, vertical_mp4_path
        )
        cvv_end_time = time.time()
        print(
            f"Clip {clip_index} vertical video creation time: {cvv_end_time - cvv_start_time:.2f} seconds")

    create_subtitles_with_ffmpeg(transcript_segments, start_time,
                                 end_time, vertical_mp4_path, subtitle_output_path, max_words=5)

    # Upload to Supabase instead of S3
    public_url = supabase_storage.upload_file(str(subtitle_output_path), output_s3_key)
    print(f"Uploaded clip to Supabase: {public_url}")
    return output_s3_key


def process_long_clip(base_dir: str, original_video_path: str, s3_key: str, start_time: float, end_time: float, clip_index: int):
    clip_name = f"clip_{clip_index}_long"
    s3_key_dir = os.path.dirname(s3_key)
    output_s3_key = f"{s3_key_dir}/long/{clip_name}.mp4"
    print(f"Output Storage key: {output_s3_key}")

    clip_dir = base_dir / clip_name
    clip_dir.mkdir(parents=True, exist_ok=True)

    clip_output_path = clip_dir / f"{clip_name}.mp4"

    duration = end_time - start_time
    # For long clips, we just cut the video without vertical cropping or subtitles
    cut_command = (f"ffmpeg -y -i \"{original_video_path}\" -ss {start_time} -t {duration} "
                   f"-c:v copy -c:a copy \"{clip_output_path}\"")
    subprocess.run(cut_command, shell=True, check=True)

    # Upload to Supabase
    public_url = supabase_storage.upload_file(str(clip_output_path), output_s3_key)
    print(f"Uploaded long clip to Supabase: {public_url}")
    return output_s3_key


@app.cls(gpu="L40S", timeout=900, retries=0, scaledown_window=20, secrets=[modal.Secret.from_name("ai-podcast-clipper-secret")], volumes={mount_path: volume})
class AiPodcastClipper:
    @modal.enter()
    def load_model(self):
        print("Loading models")

        # Automatically fallback to CPU if CUDA is not available
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        if device == "cuda":
            print("Transcription running on GPU")
        else:
            print("Transcription running on CPU")
        
        # Replaced Whisper with Faster-Whisper (Safe Initialization)
        self.whisper_model = WhisperModel(
            "base",
            device=device,
            compute_type="float16" if device == "cuda" else "int8"
        )

        print("Transcription models loaded...")

        print("Creating gemini client...")
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        
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
            available_models = ["models/gemini-flash-latest", "models/gemini-1.5-flash", "models/gemini-1.5-pro"]

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
            selected_model = "models/gemini-1.5-flash"
            
        print(f"Selected Gemini model: {selected_model}")
        self.gemini_model = genai.GenerativeModel(selected_model)
        print("Created gemini client...")

    def transcribe_video(self, base_dir: str, video_path: str) -> str:
        audio_path = base_dir / "audio.wav"
        extract_cmd = f"ffmpeg -y -i \"{video_path}\" -vn -acodec pcm_s16le -ar 16000 -ac 1 \"{audio_path}\""
        subprocess.run(extract_cmd, shell=True,
                       check=True, capture_output=True)

        print("Starting transcription with Whisper...")
        start_time = time.time()

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

        print("Transcription finished.")
        duration = time.time() - start_time
        print("Transcription took " + str(duration) + " seconds")

        return json.dumps(segments)

    def identify_moments(self, transcript: dict):
        response = self.gemini_model.generate_content("""
    This is a podcast video transcript consisting of word, along with each words's start and end time. I am looking to create clips between a minimum of 30 and maximum of 60 seconds long. The clip should never exceed 60 seconds.

    Your task is to find and extract stories, or question and their corresponding answers from the transcript.
    Each clip should begin with the question and conclude with the answer.
    It is acceptable for the clip to include a few additional sentences before a question if it aids in contextualizing the question.

    Please adhere to the following rules:
    - Ensure that clips do not overlap with one another.
    - Start and end timestamps of the clips should align perfectly with the sentence boundaries in the transcript.
    - Only use the start and end timestamps provided in the input. modifying timestamps is not allowed.
    - Format the output as a list of JSON objects, each representing a clip with 'start' and 'end' timestamps: [{"start": seconds, "end": seconds}, ...clip2, clip3]. The output should always be readable by the python json.loads function.
    - Aim to generate longer clips between 40-60 seconds, and ensure to include as much content from the context as viable.

    Avoid including:
    - Moments of greeting, thanking, or saying goodbye.
    - Non-question and answer interactions.

    If there are no valid clips to extract, the output should be an empty list [], in JSON format. Also readable by json.loads() in Python.

    The transcript is as follows:\n\n""" + str(transcript))
        print("Gemini response:", response)
        
        if not response.candidates:
            print("Warning: Gemini returned no candidates for identify_moments.")
            return "[]"
            
        print(f"Identified moments response text: {response.text}")
        return response.text

    @modal.fastapi_endpoint(method="POST")
    def process_video(self, request: ProcessVideoRequest, token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
        s3_key = request.s3_key

        # Local mode bypass for auth and s3
        is_local = os.environ.get("USE_MODAL", "0") == "0"
        
        if not is_local:
             if token.credentials != os.environ["AUTH_TOKEN"]:
                 raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                     detail="Incorrect bearer token", headers={"WWW-Authenticate": "Bearer"})

        run_id = str(uuid.uuid4())
        base_dir = pathlib.Path(tempfile.gettempdir()) / "ai-podcast-clipper" / run_id
        base_dir.mkdir(parents=True, exist_ok=True)

        # Download video file
        video_path = base_dir / "input.mp4"
        
        if is_local and s3_key.startswith("local_file:"):
            # Extract filename from key
            filename = s3_key.replace("local_file:", "")
            # Assuming file is in frontend's public/uploads
            # We need to find the absolute path. 
            # Assuming backend and frontend are in same parent dir
            # c:\Users\...\ai-podcast-clipper-backend\..\ai-podcast-clipper-frontend\public\uploads
            # But safer to assume a fixed relative path or pass absolute path
            
            # Try to find the file
            # Go up one level from backend root
            repo_root = pathlib.Path(__file__).parent.parent
            local_file_path = repo_root / "ai-podcast-clipper-frontend" / "public" / "uploads" / filename
            
            if not local_file_path.exists():
                print(f"Error: Local file not found at {local_file_path}")
                # Fallback check current dir
                local_file_path = pathlib.Path(filename)
            
            if local_file_path.exists():
                print(f"Using local file: {local_file_path}")
                shutil.copy(local_file_path, video_path)
            else:
                print(f"CRITICAL: Could not find local file {filename}")
        else:
            # s3_client = boto3.client("s3")
            # s3_client.download_file("ai-podcast-clipper", s3_key, str(video_path))
            print("S3 download disabled in favor of Supabase (or local only mode)")
            raise NotImplementedError("S3 download is disabled. Use Supabase or local upload.")

        # 1. Transcription
        transcript_segments_json = self.transcribe_video(base_dir, video_path)
        transcript_segments = json.loads(transcript_segments_json)

        # 2. Identify moments for clips
        print("Identifying clip moments")
        identified_moments_raw = self.identify_moments(transcript_segments)

        cleaned_json_string = identified_moments_raw.strip()
        if cleaned_json_string.startswith("```json"):
            cleaned_json_string = cleaned_json_string[len("```json"):].strip()
        if cleaned_json_string.endswith("```"):
            cleaned_json_string = cleaned_json_string[:-len("```")].strip()

        clip_moments = json.loads(cleaned_json_string)
        if not clip_moments or not isinstance(clip_moments, list):
            print("Error: Identified moments is not a list")
            clip_moments = []

        print(clip_moments)

        # 3. Process clips
        for index, moment in enumerate(clip_moments[:5]):
            if "start" in moment and "end" in moment:
                print("Processing clip" + str(index) + " from " +
                      str(moment["start"]) + " to " + str(moment["end"]))
                process_clip(base_dir, video_path, s3_key,
                             moment["start"], moment["end"], index, transcript_segments)

        if base_dir.exists():
            print(f"Cleaning up temp dir after {base_dir}")
            shutil.rmtree(base_dir, ignore_errors=True)


@app.local_entrypoint()
def main():
    import requests

    ai_podcast_clipper = AiPodcastClipper()

    url = ai_podcast_clipper.process_video.web_url

    payload = {
        "s3_key": "test2/mi630min.mp4"
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 123123"
    }

    response = requests.post(url, json=payload,
                             headers=headers)
    response.raise_for_status()
    result = response.json()
    print(result)


# --- Local FastAPI Setup ---

MAX_VIDEO_LENGTH_SECONDS = 6 * 60 * 60  # 6 hours

def get_video_duration(video_path: str) -> float:
    """Get video duration using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ]
        output = subprocess.check_output(cmd).decode().strip()
        return float(output)
    except Exception as e:
        print(f"Error getting duration: {e}")
        return 0.0

def split_audio_into_chunks(audio_path: pathlib.Path, base_dir: pathlib.Path, chunk_duration_sec: int = 300) -> list[pathlib.Path]:
    """Split audio into chunks of specified duration."""
    print(f"Splitting audio into {chunk_duration_sec}s chunks...")
    chunks_dir = base_dir / "audio_chunks"
    chunks_dir.mkdir(exist_ok=True)
    
    # ffmpeg command to split audio
    # -f segment -segment_time 300 -c copy out%03d.wav
    chunk_pattern = chunks_dir / "chunk_%03d.wav"
    split_cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-f", "segment", "-segment_time", str(chunk_duration_sec),
        "-c", "copy", str(chunk_pattern)
    ]
    subprocess.run(split_cmd, check=True, capture_output=True)
    
    chunks = sorted(list(chunks_dir.glob("chunk_*.wav")))
    print(f"Split into {len(chunks)} chunks.")
    return chunks

def segment_transcript(transcript: list, segment_duration: int) -> list:
    """Split transcript into segments of roughly segment_duration seconds."""
    if not transcript:
        return []
    
    segments = []
    current_segment_text = []
    current_start = transcript[0]["start"]
    
    for word_obj in transcript:
        current_segment_text.append(word_obj["word"])
        
        # If we reached the duration, close the segment
        if word_obj["end"] - current_start >= segment_duration:
            segments.append({
                "start": current_start,
                "end": word_obj["end"],
                "text": " ".join(current_segment_text)
            })
            current_segment_text = []
            # Start next segment from current end (approximate)
            current_start = word_obj["end"]
            
    # Add last bit
    if current_segment_text:
        segments.append({
            "start": current_start,
            "end": transcript[-1]["end"],
            "text": " ".join(current_segment_text)
        })
        
    return segments

if os.environ.get("USE_MODAL", "0") == "0":
    print("Initializing Local FastAPI App...")
    fastapi_app = FastAPI()
    from local_clipper import LocalAiPodcastClipper

    # Configure CORS
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Local-only clipper without Modal decorators
    clipper = LocalAiPodcastClipper()

    @fastapi_app.post("/process-video")
    async def process_video_local(file: UploadFile = File(...), clipType: str = Form("short")):
        try:
            # Ensure models are loaded once in local mode
            clipper.ensure_models_loaded()

            run_id = str(uuid.uuid4())
            base_dir = pathlib.Path(tempfile.gettempdir()) / "ai-podcast-clipper" / run_id
            base_dir.mkdir(parents=True, exist_ok=True)

            # Save uploaded file locally
            video_path = base_dir / "input.mp4"
            with open(video_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # --- Performance Safeguard: Max Length Check ---
            print("Checking video duration...")
            duration = get_video_duration(video_path)
            print(f"Video duration: {duration:.2f} seconds")
            
            if duration > MAX_VIDEO_LENGTH_SECONDS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Video too long ({duration/3600:.1f}h). Max allowed is {MAX_VIDEO_LENGTH_SECONDS/3600:.1f}h."
                )
            
            if duration > 2 * 60 * 60: # 2 hours
                print("Long podcast detected. Processing with chunked transcription.")

            # --- Audio Extraction ---
            print("Starting audio extraction...")
            audio_path = base_dir / "audio.wav"
            # ffmpeg -i input_video.mp4 -vn -acodec pcm_s16le -ar 16000 audio.wav
            extract_cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                str(audio_path)
            ]
            subprocess.run(extract_cmd, check=True, capture_output=True)
            print("Audio extraction complete.")

            # --- Long Video Support: Audio Chunking ---
            chunks = []
            if duration > 1800: # 30 minutes
                print("Video is long (>30m), splitting into chunks for transcription...")
                chunks = split_audio_into_chunks(audio_path, base_dir)
            else:
                chunks = [audio_path]

            # --- Transcription ---
            print(f"Starting transcription of {len(chunks)} chunk(s)...")
            full_transcript = []
            for i, chunk in enumerate(chunks):
                print(f"Transcribing chunk {i+1} of {len(chunks)}...")
                # Faster-Whisper returns a generator of segments
                segments_gen, info = clipper.whisper_model.transcribe(
                    str(chunk),
                    language="en",
                    beam_size=5,
                    vad_filter=True
                )
                
                chunk_transcript = []
                # Consume the generator to get segments
                for segment in segments_gen:
                    text = segment.text.strip()
                    if not text:
                        continue
                    
                    # Merge logic with timestamp offset
                    offset = i * 300 # 5 minutes
                    seg_start = segment.start + offset
                    seg_end = segment.end + offset
                    
                    words = text.split()
                    if not words:
                        continue
                        
                    seg_duration = seg_end - seg_start
                    word_duration = seg_duration / len(words)
                    
                    current_time = seg_start
                    for word in words:
                        chunk_transcript.append({
                            "start": current_time,
                            "end": current_time + word_duration,
                            "word": word
                        })
                        current_time += word_duration
                
                print(f"Chunk produced {len(chunk_transcript)} word segments")
                full_transcript.extend(chunk_transcript)
                
            print(f"Total transcript segments: {len(full_transcript)}")
            print("Transcription finished.")

            # --- Transcript Segmentation ---
            # short -> 60-90s, long -> 3-4m
            seg_duration = 75 if clipType == "short" else 210
            print(f"Segmenting transcript into {seg_duration}s chunks for AI analysis...")
            segments = segment_transcript(full_transcript, seg_duration)
            print(f"Total segments: {len(segments)}")

            # --- Gemini AI Segment Scoring ---
            print("Scoring segments using Gemini AI in parallel...")
            scored_segments = []
            
            def score_one(seg):
                try:
                    score_data = clipper.score_segment(seg["text"])
                    return {
                        **seg,
                        "score": score_data.get("score", 50),
                        "hook": score_data.get("hook", ""),
                        "category": score_data.get("category", "insight"),
                        "reason": score_data.get("reason", "")
                    }
                except Exception as e:
                    print(f"Parallel scoring error for segment: {e}")
                    return {
                        **seg,
                        "score": 50,
                        "hook": "",
                        "category": "insight",
                        "reason": f"Parallel error: {str(e)}"
                    }

            # Use ThreadPoolExecutor for parallel scoring
            with ThreadPoolExecutor(max_workers=5) as executor:
                scored_segments = list(executor.map(score_one, segments))

            # --- Rank Segments ---
            print("Ranking segments and selecting top viral moments...")
            scored_segments.sort(key=lambda x: x["score"], reverse=True)
            
            # Dynamic clip count based on video duration - limit to top 4 for quality
            num_clips = 4
            
            print(f"Total segments detected: {len(segments)}")
            print(f"Selected top {num_clips} segments for clips")
            
            top_segments = []
            for seg in scored_segments:
                if len(top_segments) >= num_clips:
                    break
                
                # Check for significant overlap with already selected segments
                is_overlapping = False
                for selected in top_segments:
                    # Calculate overlap
                    overlap_start = max(seg["start"], selected["start"])
                    overlap_end = min(seg["end"], selected["end"])
                    if overlap_end > overlap_start:
                        overlap_duration = overlap_end - overlap_start
                        # If overlap is more than 20% of the current segment, skip it
                        if overlap_duration > (seg["end"] - seg["start"]) * 0.2:
                            is_overlapping = True
                            break
                
                if not is_overlapping:
                    top_segments.append(seg)
            
            # --- Clip Duration Logic & Padding ---
            # short -> 40-60s, long -> 4-6m
            min_dur = 40 if clipType == "short" else 240
            max_dur = 60 if clipType == "short" else 360
            
            clips = []
            original_key = f"uploads/{run_id}/{file.filename}"

            # --- Clip Generation & Supabase Upload ---
            for i, seg in enumerate(top_segments):
                print(f"Generating clip {i+1}/{len(top_segments)}...")
                
                # Expand boundaries slightly for context
                # Padding of 10s as requested
                start = max(0, seg["start"] - 10)
                # For long clips, we already have a long segment, but let's ensure bounds
                duration_clip = random.randint(min_dur, max_dur)
                end = min(start + duration_clip, duration)
                
                # Re-calculate to ensure it doesn't exceed video length
                if end > duration:
                    end = duration
                    start = max(0, end - duration_clip)
                
                # Prevent empty clips
                if end <= start:
                    print(f"Skipping invalid clip segment {i+1}: start={start}, end={end}")
                    continue

                if clipType == "short":
                    output_key = process_clip(base_dir, video_path, original_key,
                                 start, end, i, full_transcript)
                else:
                    output_key = process_long_clip(base_dir, video_path, original_key,
                                      start, end, i)
                
                clips.append({
                    "s3Key": output_key,
                    "clipType": clipType or "short"
                })
            
            # --- Cleanup ---
            if base_dir.exists():
                print(f"Cleaning up temporary files in {base_dir}...")
                shutil.rmtree(base_dir, ignore_errors=True)
                
            return {
                "success": True,
                "clips": clips
            }

        except Exception as e:
            print(f"CRITICAL ERROR in pipeline: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal Server Error: {str(e)}"
            )

    # For uvicorn to pick up 'app'
    app = fastapi_app 
    print("Local FastAPI 'app' is ready.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
