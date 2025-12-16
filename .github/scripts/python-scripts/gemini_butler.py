import os
import requests
from google import genai

def main():
    # 1. Setup Configuration
    github_token = os.environ["GITHUB_TOKEN"]
    gemini_key = os.environ["GEMINI_API_KEY"]
    repo = os.environ["REPO"]

    # Inputs
    raw_comment = os.environ["COMMENT_BODY"]
    event_name = os.environ["EVENT_NAME"]
    pr_issue_number = os.environ["PR_OR_ISSUE_NUMBER"]
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
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=f"You are a helpful coding assistant. The user said: {user_question}"
        )
        reply_text = response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        return

    # --- 2. Post Reply to GitHub ---
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # LOGIC SWITCH: Handle the different API endpoints
    if event_name == "issue_comment":
        # === FIX FOR 404 ===
        # For general conversation, we post to the ISSUE endpoint, not the comment endpoint.
        url = f"https://api.github.com/repos/{repo}/issues/{pr_issue_number}/comments"
        payload = {
            "body": f"> {user_question}\n\n**Gemini:**\n{reply_text}"
        }
        print("Detected Issue/PR Conversation comment.")

    elif event_name == "pull_request_review_comment":
        # For code review, we reply to the specific thread.
        url = f"https://api.github.com/repos/{repo}/pulls/comments/{comment_id}/replies"
        payload = {
            "body": f"**Gemini:**\n{reply_text}"
        }
        print("Detected Code Review comment.")
    
    else:
        print(f"Unknown event: {event_name}")
        return
    
    print(f"Posting to: {url}")
    
    r = requests.post(url, json=payload, headers=headers)
    
    # Print response for debugging if it fails
    if r.status_code != 201:
        print(f"Failed with {r.status_code}: {r.text}")
        
    r.raise_for_status()
    print("Success!")
    
        
if __name__ == "__main__":
    main()