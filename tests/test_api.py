import json, urllib.request, urllib.error

def test_api():
    appName = "attention_triage_agent"
    userId = "test-user"
    sessionId = "test-session-" + str(int(urllib.request.time.time()))

    print(f"1. Creating session: {sessionId}")
    req_create = urllib.request.Request(
        f"http://localhost:8083/apps/{appName}/users/{userId}/sessions/{sessionId}", 
        method="POST", 
        data=json.dumps({}).encode(), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req_create) as res:
            print("Session Created:", res.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Session Create Error {e.code}:", e.read().decode())
        return

    print("\n2. Running Agent with correct Content/Part payload...")
    payload = {
        "appName": appName,
        "userId": userId,
        "sessionId": sessionId,
        "new_message": {
            "parts": [{"text": "hello, perform triage on: 1) Urgent email from boss"}]
        }
    }
    
    req_run = urllib.request.Request(
        "http://localhost:8083/run", 
        method="POST", 
        data=json.dumps(payload).encode(), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req_run) as run_res:
            print("200 OK Response Received!")
            # print(run_res.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Run Error {e.code}:", e.read().decode())

if __name__ == "__main__":
    test_api()
