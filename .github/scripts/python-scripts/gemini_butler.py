import os
import requests
from google import genai

def main():
    # 1. Setup Configuration
    github_token = os.environ["GITHUB_TOKEN"]
    gemini_key = os.environ["GEMINI_API_KEY"]
    raw_comment = os.environ["COMMENT_BODY"]
    repo = os.environ["REPO"]
    comment_id = os.environ["COMMENT_ID"]
    
    # 2. Configure Gemini
    client = genai.Client(api_key=gemini_key)

    # 3. Prepare the Prompt
    # Remove the trigger phrase '/ask' to get the actual question
    user_question = raw_comment.replace('/ask', '').strip()
    
    if not user_question:
        print("No question found after /ask")
        return

    print(f"Asking Gemini: {user_question}")

    try:
        # 4. Generate Content
        # You can add system instructions here if you want it to act like a specific persona
        response = client.models.generate_content(
            model = "gemini-2.5-flash",
            contents =   f"You are a helpful coding assistant in a GitHub Pull Request. "
                        f"The user said: {user_question}"
        )
        reply_text = response.text

        # 5. Post Reply to GitHub
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # We reply to the specific comment ID to keep it threaded
        url = f"https://api.github.com/repos/{repo}/pulls/comments/{comment_id}/replies"
        
        data = {
            "body": f"**Gemini:**\n{reply_text}"
        }

        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
        print("Reply posted successfully.")

    except Exception as e:
        print(f"Error: {e}")
        # Optional: Post error back to PR so you know it failed
        
if __name__ == "__main__":
    main()