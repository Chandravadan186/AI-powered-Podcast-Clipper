import os
import google.generativeai as genai
from dotenv import load_dotenv

print("Script started")

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print("API key:", api_key)

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.5-flash")

response = model.generate_content("Say hello")

print("Response:", response.text)