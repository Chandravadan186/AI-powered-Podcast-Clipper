


This project has been configured to run locally without external dependencies like Modal, S3, or Authentication providers.



1.  **Node.js** (v18+)
2.  **Python** (3.10+)
3.  **FFmpeg** (Required for video processing)
    *   **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your System PATH.
    *   **Mac**: `brew install ffmpeg`
    *   **Linux**: `sudo apt install ffmpeg`



Open a terminal in `ai-podcast-clipper-frontend`:

```bash
cd ai-podcast-clipper-frontend
npm install --legacy-peer-deps
npx prisma generate
npx prisma db push
npx tsx prisma/seed.ts  # Seeds a local user with credits
npm run dev
```

The frontend will run at [http://localhost:3000](http://localhost:3000).
It will automatically redirect to `/dashboard`.



Open a new terminal in `ai-podcast-clipper-backend`:

```bash
cd ai-podcast-clipper-backend
pip install -r requirements.txt
# If you encounter issues, install manually:
# pip install fastapi uvicorn boto3 modal ffmpegcv numpy google-genai pysubs2 tqdm whisperx opencv-python
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```







