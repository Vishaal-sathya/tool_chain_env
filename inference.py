import requests
import json
import time

API_BASE_URL = "http://localhost:7860"

def run_benchmarking():
    tasks = ["task1", "task2", "task3"]
    
    for task in tasks:
        # MANDATORY LOGGING FORMAT
        print(f"\n[START] Mission: {task}")
        
        try:
            res = requests.post(f"{API_BASE_URL}/reset", json={"task_id": task}, timeout=10)
            obs = res.json()["observation"]
        except Exception as e:
            print(f"FAILED TO CONNECT: {e}")
            continue

        step_count = 0
        max_steps = 10
        total_score = 0.0

        while step_count < max_steps:
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": json.dumps(obs)}]
            }
            
            try:
                llm_res = requests.post(f"{API_BASE_URL}/v1/chat/completions", json=payload, timeout=10)
                content = llm_res.json()["choices"][0]["message"]["content"]
                action_data = json.loads(content)
            except Exception as e:
                print(f"Decision Error: {e}")
                break

            try:
                step_res = requests.post(f"{API_BASE_URL}/step", json=action_data, timeout=10)
                data = step_res.json()
                
                obs = data["observation"]
                total_score = data["info"]["score"]
                done = data["done"]
                
                # MANDATORY LOGGING FORMAT
                print(f"[STEP] {step_count+1}: {action_data['action'].get('method')} {action_data['action'].get('endpoint')} | Status: {obs['status_code']} | Local_Score: {total_score}")
                
                step_count += 1
                if done: break
                time.sleep(0.5)
            except Exception as e:
                print(f"Execution Error: {e}")
                break

        print(f"[END] Mission {task} | Final Score: {total_score}\n")

if __name__ == "__main__":
    run_benchmarking()
