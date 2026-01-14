import sys
import json
import os
from openai import OpenAI

def main():
    # Read input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}), file=sys.stderr)
        return

    api_key = input_data.get("api_key")
    model = input_data.get("model")
    instructions = input_data.get("instructions")
    file_paths = input_data.get("file_paths", [])

    if not api_key:
        print(json.dumps({"error": "Missing API Key"}), file=sys.stderr)
        return

    # Initialize Client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Build Context
    messages = [{"role": "system", "content": instructions}]
    
    file_content_str = ""
    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                file_content_str += f"\n--- FILE: {os.path.basename(path)} ---\n{content}\n"
        except Exception as e:
            file_content_str += f"\n--- ERROR READING {path}: {str(e)} ---\n"

    if file_content_str:
        messages.append({"role": "user", "content": f"Here is the context data:\n{file_content_str}"})
    
    # Just a simple prompt to trigger the subagent
    messages.append({"role": "user", "content": "Please analyze the provided context and respond to the instructions."})

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        response = completion.choices[0].message.content
        print(json.dumps({"result": response}))
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)

if __name__ == "__main__":
    main()
