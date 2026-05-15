import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import supabase
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase python package not found. Please run: pip install -r requirements.txt")
    sys.exit(1)

def test_connection():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file")
        return

    print(f"Testing connection to Supabase...")
    print(f"URL: {url}")
    # Mask key for security
    print(f"Key: {key[:5]}...{key[-5:] if len(key) > 10 else ''}")

    try:
        supabase: Client = create_client(url, key)
        
        # storage bucket name
        BUCKET_NAME = os.environ.get("SUPABASE_BUCKET_NAME", "videos")
        
        print(f"Attempting to list files in bucket '{BUCKET_NAME}'...")
        res = supabase.storage.from_(BUCKET_NAME).list()
        
        print("Connection successful!")
        print(f"Found {len(res)} items in root of bucket '{BUCKET_NAME}'")
        
        # Test upload
        test_filename = "test_connection_check.txt"
        with open(test_filename, "w") as f:
            f.write("This is a test file to verify Supabase Storage connection.")
            
        print(f"Attempting to upload test file '{test_filename}'...")
        with open(test_filename, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(test_filename, f, {"upsert": "true"})
            
        print("Upload successful!")
        
        # Get public URL
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(test_filename)
        print(f"Public URL: {public_url}")
        
        # Clean up
        print("Cleaning up test file...")
        supabase.storage.from_(BUCKET_NAME).remove([test_filename])
        os.remove(test_filename)
        print("Cleanup successful!")
        print("\n✅ Supabase integration verified successfully!")

    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        print("\nTroubleshooting tips:")
        print("1. Check if your SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are correct in .env")
        print("2. Ensure the Storage Bucket 'videos' exists in your Supabase project")
        print("3. Check your RLS (Row Level Security) policies for the Storage bucket")

if __name__ == "__main__":
    test_connection()
