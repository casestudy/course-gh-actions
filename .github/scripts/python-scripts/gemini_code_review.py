import os
import requests
import json
from google import genai
from google.genai import types

def get_pr_diff(repo, pr_number, github_token):
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def post_review(repo, pr_number, github_token, comments, general_summary):
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    payload = {
        "event": "COMMENT",
        "body": f"## ⚡ Gemini 2.5 Flash Review\n\n{general_summary}",
        "comments": comments
    }

    print(f"Submitting review with {len(comments)} inline comments...")
    r = requests.post(url, json=payload, headers=headers)
    
    if r.status_code not in [200, 201]:
        print(f"❌ Review failed. Status: {r.status_code}, Response: {r.text}")
        # Fallback: Post as general comment
        url_fallback = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        requests.post(url_fallback, json={"body": payload["body"]}, headers=headers)
    else:
        print("✅ Review submitted successfully!")

def main():
    # --- Configuration ---
    github_token = os.environ["GITHUB_TOKEN"]
    gemini_key = os.environ["GEMINI_API_KEY"]
    repo = os.environ["REPO"]
    
    # Inputs
    raw_comment = os.environ["COMMENT_BODY"]
    pr_issue_number = os.environ["PR_OR_ISSUE_NUMBER"]
    
    if not raw_comment.strip().startswith('/review'):
        print("Not a /review command. Skipping.")
        return

    client = genai.Client(api_key=gemini_key)
    
    # 1. Fetch Diff
    try:
        diff_text = get_pr_diff(repo, pr_issue_number, github_token)
    except Exception as e:
        print(f"Diff fetch failed: {e}")
        return

    print("Asking Gemini 2.5 Flash to review...")

    # 2. Prompt for JSON Output
    prompt = (
        "You are a strict Senior Software Engineer Code Reviewer. Review this git diff. "
        "Your goal is to identify **ALL** bugs, security vulnerabilities, logic errors, unused variables or dead code, and code style violations.\n\n"
        
        "IMPORTANT INSTRUCTIONS:\n"
        "1. **Be Exhaustive:** Do not stop after finding one error. Scan the entire diff from top to bottom.\n"
        "2. **Multiple Comments:** If there are 5 different bugs, output 5 different inline comments.\n"
        "3. **Strict JSON:** You must respond in valid JSON format only.\n"
        "4. **Line Numbers:** 'line' must be the exact line number in the new code (lines starting with +).\n\n"

        "Output Structure:\n"
        "{\n"
        "  \"summary\": \"High-level summary of the changes.\",\n"
        "  \"action\": \"APPROVE | REQUEST_CHANGES | COMMENT\",\n"
        "  \"comments\": [\n"
        "    {\"path\": \"filename.py\", \"line\": 10, \"body\": \"Fix this variable name.\"},\n"
        "    {\"path\": \"filename.py\", \"line\": 45, \"body\": \"Potential SQL injection here.\"}\n"
        "  ]\n"
        "}\n\n"
        f"DIFF:\n{diff_text}"
    )

    try:
        # 3. Call Gemini 2.5 Flash
        response = client.models.generate_content(
            model='gemini-2.5-flash', # <--- UPDATED MODEL NAME
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=4000  # Ensure enough space for long lists
            )
        )
        
        data = json.loads(response.text)
        summary = data.get("summary", "Code Review")
        inline_comments = data.get("comments", [])

        # If Gemini generates multiple comments for the same file/line, we merge them.
        merged_map = {} # Key: (path, line) -> Comment Dict
        
        for item in inline_comments:
            path = item.get('path')
            line = item.get('line')
            body = item.get('body')
            
            if not path or not line or not body:
                continue

            key = (path, line)
            
            if key in merged_map:
                # If a comment already exists for this line, append the new body
                existing_body = merged_map[key]['body']
                merged_map[key]['body'] = f"{existing_body}\n\n---\n\n{body}"
            else:
                # Otherwise, start a new entry
                merged_map[key] = item

        # Convert the dictionary back to a list
        final_comments = list(merged_map.values())

    except Exception as e:
        print(f"Gemini processing error: {e}")
        summary = f"Error parsing Gemini response: {e}"
        final_comments = []

    # 4. Submit to GitHub
    post_review(repo, pr_issue_number, github_token, final_comments, summary)

if __name__ == "__main__":
    main()