from google import genai
from google.genai import types
from src import config

def __init__(self):
        self.client = genai.Client( vertexai=True, project=config.app.GOOGLE_CLOUD_PROJECT, location=config.app.GOOGLE_CLOUD_REGION)