import requests
import json

BASE_URL = "http://localhost:7860"
__test__ = False

def test_interactive():
    print("--- ToolChain-Env Interactive Test ---")
    
    # 1. Reset
    task_id = input("Enter Task ID (1, 2, or 3) [default 1]: ") or "1"
    response = requests.post(f"{BASE_URL}/reset?task_id={task_id}")
    print("\n[RESET RESPONSE]")
    print(json.dumps(response.json(), indent=2))
    
    while True:
        print("\n--- Enter Action (or 'exit' to quit) ---")
        method = input("Method (GET/POST) [default GET]: ").upper() or "GET"
        if method == "EXIT": break
        
        endpoint = input("Endpoint (e.g. /api/auth): ")
        if not endpoint.startswith("/"): endpoint = "/" + endpoint
        
        headers_str = input("Headers JSON (e.g. {'Authorization': 'Bearer ...'}) [default {}]: ") or "{}"
        try:
            headers = json.loads(headers_str.replace("'", "\""))
        except:
            print("Invalid JSON headers, using {}")
            headers = {}
            
        body_str = input("Body JSON [default {}]: ") or "{}"
        try:
            body = json.loads(body_str.replace("'", "\""))
        except:
            print("Invalid JSON body, using {}")
            body = {}
            
        # 2. Step
        payload = {
            "action": {
                "method": method,
                "endpoint": endpoint,
                "headers": headers,
                "body": body
            }
        }
        
        print(f"\nSending {method} to {endpoint}...")
        step_res = requests.post(f"{BASE_URL}/step", json=payload)
        
        if step_res.status_code == 200:
            data = step_res.json()
            print("\n[STEP RESULT]")
            print(f"Status Code: {data['observation']['status_code']}")
            print(f"Response: {json.dumps(data['observation']['response_data'])}")
            print(f"Reward: {data['reward']}")
            print(f"Score: {data['info']['score']}")
            print(f"Done: {data['done']}")
        else:
            print(f"Error: {step_res.status_code} - {step_res.text}")

if __name__ == "__main__":
    try:
        test_interactive()
    except Exception as e:
        print(f"Connection failed: {e}. Is the server running on port 7860?")
