# Supabase Setup & Migration Guide

This project has been migrated from AWS S3 to Supabase Storage for file handling. Follow these steps to set up your local environment.

## 1. Supabase Project Setup

1.  **Create a Supabase Project**: Go to [database.new](https://database.new) and create a new project.
2.  **Create a Storage Bucket**:
    *   Go to **Storage** in the sidebar.
    *   Create a new bucket named `podcast-uploads`.
    *   **Public Access**: Ensure the bucket is set to **Public** so files can be accessed via URL.
3.  **Storage Policies** (Important for Security, though technically optional for public read if "Public" is checked):
    *   Allow public read access (if not already enabled by the "Public" setting).
    *   Allow upload/insert access for authenticated/service role (we use the Service Role key in the backend, so it bypasses RLS, but you can set policies if you use the client key).

## 2. Environment Variables

### Backend (`ai-podcast-clipper-backend/.env`)

Update your backend `.env` file with your Supabase credentials. You can find these in Project Settings > API.

```env
GEMINI_API_KEY="your_gemini_key"
AUTH_TOKEN="123123"
USE_MODAL="0"

# Supabase Configuration
SUPABASE_URL="https://your-project-ref.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key-starts-with-ey..."
SUPABASE_BUCKET="podcast-uploads"
```

*   **Note**: Use the `service_role` key (secret) for the backend to allow full access to the bucket without RLS restrictions.

### Frontend (`ai-podcast-clipper-frontend/.env`)

Update your frontend `.env` file.

```env
DATABASE_URL="file:./dev.db"
BASE_URL="http://localhost:3000"

# Backend Connection
PROCESS_VIDEO_ENDPOINT="http://127.0.0.1:8000/process-video"
PROCESS_VIDEO_ENDPOINT_AUTH="123123"
NEXT_PUBLIC_API_URL="http://127.0.0.1:8000"

# Supabase Configuration (Public)
NEXT_PUBLIC_SUPABASE_URL="https://your-project-ref.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="your-anon-key-starts-with-ey..."
```

## 4. Verification

We have provided a script to verify your Supabase connection and Storage bucket configuration.

1. Navigate to the backend directory:
   ```bash
   cd ai-podcast-clipper-backend
   ```
2. Run the verification script:
   ```bash
   python test_supabase_connection.py
   ```

If successful, you will see a "Connection successful!" message and a test file upload/deletion.

## 5. Running the Project

### Backend

1.  Navigate to `ai-podcast-clipper-backend`.
2.  Install dependencies (if not already installed):
    ```bash
    pip install fastapi uvicorn python-multipart supabase
    ```
3.  Run the server:
    ```bash
    python main.py
    ```
    The server will start at `http://127.0.0.1:8000`.

### Frontend

1.  Navigate to `ai-podcast-clipper-frontend`.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Run the development server:
    ```bash
    npm run dev
    ```
    The app will be available at `http://localhost:3000`.

## 4. How it Works (Architecture Change)

*   **Uploads**: Files are now uploaded directly from the Frontend to the Backend (`/process-video` endpoint).
*   **Storage**: The Backend uploads the original file and generated clips to **Supabase Storage**.
*   **Database**: The Frontend stores the public Supabase URLs in the local SQLite database (`s3Key` field now holds the full URL).
*   **Display**: The Frontend serves the video/clips directly using the Supabase Public URLs.

## 5. Troubleshooting

*   **CORS Errors**: Ensure `NEXT_PUBLIC_API_URL` matches your backend URL. The backend is configured to allow `localhost:3000`.
*   **Upload Failures**: Check your `SUPABASE_SERVICE_ROLE_KEY` in the backend `.env`. It must be the Service Role key, not the Anon key, for backend uploads.
*   **Prisma Errors**: If you see DB errors, run `npx prisma generate && npx prisma db push` in the frontend directory to ensure your local SQLite DB is synced.
