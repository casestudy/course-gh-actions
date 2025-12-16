import os
import requests
from google import genai
from google.genai import types
import json

def get_pr_diff(repo, pr_number, github_token):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3.diff"  # <--- Important: Asks GitHub for the raw diff
    }
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def post_review(repo, pr_number, github_token, comments, general_summary):
    """
    Submits a formal GitHub Review with inline comments.
    """
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # payload for the review
    payload = {
        "event": "COMMENT", # Options: APPROVE, REQUEST_CHANGES, COMMENT
        "body": f"## 🤖 Gemini Code Review Summary\n\n{general_summary}",
        "comments": comments
    }

    print(f"Submitting review with {len(comments)} inline comments...")
    r = requests.post(url, json=payload, headers=headers)
    
    # If line numbers are wrong, GitHub rejects the WHOLE review. 
    # Fallback: Post just the summary if strict review fails.
    if r.status_code not in [200, 201]:
        print(f"❌ Review failed (likely invalid line numbers). Status: {r.status_code}")
        print(f"Response: {r.text}")
        print("Fallback: Posting general comment only.")
        
        # Fallback URL (Issue Comment)
        url_fallback = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        requests.post(url_fallback, json={"body": payload["body"]}, headers=headers)
    else:
        print("✅ Review submitted successfully!")

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
    # Check if the comment starts with /ask or /review
    triggered = raw_comment.strip().startswith('/ask') or raw_comment.strip().startswith('/review')  
    if raw_comment.strip().startswith('/ask'):
        triggered = "ask"
    elif raw_comment.strip().startswith('/review'):
        triggered = "review"
    else:
        triggered = ""

    if triggered == "ask":
        # Remove the trigger phrase '/ask' to get the actual question
        user_question = raw_comment.replace('/ask', '').strip()
        
        if not user_question:
            print("No question found after /ask")
            return

        print(f"Asking Gemini: {user_question}")

        prompt = f"You are a helpful coding assistant. The user said: {user_question}"

    elif triggered == "review":
        print(f"Starting Full Code Review for PR #{pr_issue_number}...")
        
        # 1. Fetch the Code Diff
        try:
            diff_text = get_pr_diff(repo, pr_issue_number, github_token)

        except Exception as e:
            print(f"Failed to fetch diff: {e}")
            return

        print("Asking Gemini to review...")
        
        # 2. Prompt for JSON Output
        # We ask for a JSON object with a summary and a list of inline comments.
        prompt = (
            "You are a Senior Software Engineer. Review this git diff. "
            "Identify bugs, security issues, and bad practices. "
            "IMPORTANT: You must respond in valid JSON format only.\n\n"
            "Output Structure:\n"
            "{\n"
            "  \"summary\": \"A brief markdown summary of the overall code quality.\",\n"
            "  \"comments\": [\n"
            "    {\"path\": \"filename.py\", \"line\": 10, \"body\": \"Comment about this line\"}\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "1. 'line' must be an integer. It must be a line number that exists in the CHANGED part of the file (added lines).\n"
            "2. Do not comment on unchanged code (lines without a '+').\n"
            "3. If you are unsure of the line number, put the comment in the 'summary' instead.\n"
            "\n"
            f"DIFF:\n{diff_text}"
        )

    else:
        print("No command found (starts with /ask or /review). Exiting.")
        return
    
    try:
        if triggered == "review":
            response = client.models.generate_content(
                model='gemini-2.5-flash', # <--- UPDATED MODEL NAME
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            data = json.loads(response.text)
            summary = data.get("summary", "Code Review")
            inline_comments = data.get("comments", [])

            # 4. Submit to GitHub
            post_review(repo, pr_issue_number, github_token, inline_comments, summary)
        else:
            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=prompt
            )
            reply_text = response.text

    except Exception as e:
        print(f"Gemini Error: {e}")
        return
    
    # --- Post Reply to GitHub ---
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # LOGIC SWITCH: Handle the different API endpoints
    if event_name == "issue_comment" or triggered == "/review":

        if event_name == "issue_comment":
            # For general conversation, we post to the ISSUE endpoint, not the comment endpoint.
            url = f"https://api.github.com/repos/{repo}/issues/{pr_issue_number}/comments"
            payload = {
                "body": f"**Gemini Code Review:**\n{reply_text}"
            }
        else:
            try:
                # Request JSON mode explicitly
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                # Parse JSON
                data = json.loads(response.text)
                summary = data.get("summary", "Code Review")
                inline_comments = data.get("comments", [])

            except Exception as e:
                print(f"Gemini processing error: {e}")
                # Fallback to plain text error
                summary = f"Error parsing Gemini response: {e}"
                inline_comments = []

            # 3. Submit to GitHub
            post_review(repo, pr_issue_number, github_token, inline_comments, summary)

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