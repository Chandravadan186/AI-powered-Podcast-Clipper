import os
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
if url and not url.endswith("/"):
    url += "/"
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
bucket_name: str = os.environ.get("SUPABASE_BUCKET", "podcast-uploads")

if not url or not key:
    raise ValueError("Supabase URL and Key must be set in environment variables.")

supabase: Client = create_client(url, key)

def upload_file(local_path: str, dest_path: str) -> str:
    """
    Uploads a file from local filesystem to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    print(f"[Supabase] Starting upload_file: local_path={local_path}, dest_path={dest_path}, bucket={bucket_name}")
    try:
        with open(local_path, 'rb') as f:
            # Correct signature: upload(path, file, options)
            res = supabase.storage.from_(bucket_name).upload(dest_path, f, {"upsert": "true"})
        print(f"[Supabase] Upload response: {res}")
        public_url = get_public_url(dest_path)
        print(f"[Supabase] Public URL: {public_url}")
        return public_url
    except Exception as e:
        print(f"[Supabase] Upload failed for {dest_path}: {e}")
        raise

def upload_bytes(data: bytes, dest_path: str) -> str:
    """
    Uploads bytes data to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    print(f"[Supabase] Starting upload_bytes: len={len(data)}, dest_path={dest_path}, bucket={bucket_name}")
    try:
        res = supabase.storage.from_(bucket_name).upload(dest_path, data, {"upsert": "true"})
        print(f"[Supabase] Upload bytes response: {res}")
        public_url = get_public_url(dest_path)
        print(f"[Supabase] Public URL: {public_url}")
        return public_url
    except Exception as e:
        print(f"[Supabase] Upload bytes failed for {dest_path}: {e}")
        raise

def get_public_url(dest_path: str) -> str:
    """
    Gets the public URL for a file in Supabase Storage.
    """
    return supabase.storage.from_(bucket_name).get_public_url(dest_path)
