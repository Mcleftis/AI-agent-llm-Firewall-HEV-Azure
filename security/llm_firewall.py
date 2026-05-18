import json
import requests
import re

def validate_input(user_input):
    if len(user_input) > 100:
        return False, "Blocked: Input length."
    
    if not re.match(r"^[a-zA-Z0-9 \.,\?_]+$", user_input):
        return False, "Blocked: Invalid characters."
        
    return True, ""

def validate_output(llm_response):
    try:
        data = json.loads(llm_response)
        action = data.get("action", "")
        
        allowed_actions = ["engage_eco_mode", "status_check", "reduce_speed"]
        
        if action not in allowed_actions:
            return False, f"Blocked: Action '{action}' not in whitelist."
            
        return True, data
    except json.JSONDecodeError:
        return False, "Blocked: Invalid JSON output."

def query_llama_secure(user_input):
    is_valid_in, msg_in = validate_input(user_input)
    if not is_valid_in:
        return msg_in

    system_prompt = """
    Return ONLY a JSON object with an "action" key.
    The action MUST be exactly one of: "engage_eco_mode", "status_check", "reduce_speed".
    """
    
    full_prompt = f"{system_prompt}\n###\n{user_input}\n###"

    try:
        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": full_prompt,
                "stream": False
            },
            timeout=30
        )
        response.raise_for_status()
        llm_text = response.json().get("response", "")
    except Exception:
        return "System Error"

    is_valid_out, out_data = validate_output(llm_text)
    if not is_valid_out:
        return out_data
        
    return f"Success: {out_data['action']}"