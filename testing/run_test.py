import requests
import re
import os
import time

# --- SETTINGS ---
HOST = "http://localhost"
PROBLEM_CODE = "test"
USERS_COUNT = 6
PASSWORD = "testpassword123"
NEW_PASSWORD = PASSWORD + "new"

CSRF_PATTERN = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')

def get_csrf(session, url):
    """Fetches the CSRF token directly from Django cookies (100% reliable)."""
    response = session.get(url)
    
    # Check if Django set the cookie automatically
    if 'csrftoken' in session.cookies:
        return session.cookies['csrftoken']
        
    # Fallback to a very aggressive regex just in case
    match = re.search(r'csrfmiddlewaretoken.*?value=["\']([^"\']+)["\']', response.text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
        
    match = re.search(r'value=["\']([^"\']+)["\'].*?csrfmiddlewaretoken', response.text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
        
    return None

def get_code(index):
    solution_dir = "tests"
    
    file_num = ((index - 1) % 3) + 1
    
    filename = os.path.join(solution_dir, f"{index}.py")
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source_code = f.read()         
            return source_code
    except FileNotFoundError:
        return ""


def run_test():
    sessions = []
    
    print("--- PHASE 1: Authentication & Security Bypass ---")
    for i in range(1, USERS_COUNT + 1):
        username = f"student_{i}"
        session = requests.Session()
        
        # 1. Login
        login_url = f"{HOST}/accounts/login/"
        csrf_token = get_csrf(session, login_url)
        
        login_data = {
            "username": username,
            "password": PASSWORD,
            "csrfmiddlewaretoken": csrf_token
        }
        
        response = session.post(login_url, data=login_data, headers={"Referer": login_url}, allow_redirects=False)
        
        # Django returns 302 on successful login
        if response.status_code == 302:
            print(f"[+] [{username}] Logged in successfully.")
            
            # --- PHASE 1.5: Forced Password Change Bypass ---
            # Probe a protected page to see if we get redirected to password change
            probe_url = f"{HOST}/problem/{PROBLEM_CODE}/submit"
            probe_resp = session.get(probe_url, allow_redirects=False)
            
            if probe_resp.status_code == 302 and 'password/change' in probe_resp.headers.get('Location', ''):
                print(f"    [*] DMOJ is forcing a password change. Automating bypass...")
                pw_url = f"{HOST}/accounts/password/change/"
                csrf_pw = get_csrf(session, pw_url)
                
                pw_data = {
                    "old_password": PASSWORD,
                    "new_password1": NEW_PASSWORD,
                    "new_password2": NEW_PASSWORD,
                    "csrfmiddlewaretoken": csrf_pw
                }
                
                # Submit the new password
                pw_change_resp = session.post(pw_url, data=pw_data, headers={"Referer": pw_url}, allow_redirects=False)
                
                if pw_change_resp.status_code == 302:
                    print(f"    [+] Security bypassed! Password updated.")
                else:
                    print(f"    [!] Failed to change password. Skipping user.")
                    continue
            
            sessions.append((username, session))
        else:
            print(f"[-] [{username}] Login failed! (Status {response.status_code})")

    if not sessions:
        print("No users authenticated. Aborting test.")
        return

    print("\n--- PHASE 2: Submitting A+B Solutions ---")
    submit_url = f"{HOST}/problem/{PROBLEM_CODE}/submit"
    
    for index, (username, session) in enumerate(sessions, start=1):
        csrf_token = get_csrf(session, submit_url)
        source_code = get_code(index)
        
        payload = {
            "language": "8", # python
            "source": source_code,
            "csrfmiddlewaretoken": csrf_token
        }
        
        print(f"[*] Sending submission #{index} from {username}...")
        
        response = session.post(submit_url, data=payload, allow_redirects=False, headers={"Referer": submit_url})
        
        if response.status_code == 302:
            redirect_target = response.headers.get('Location', '')
            if 'password/change' in redirect_target:
                print(f"    -> [!] Still blocked by password wall! Target: {redirect_target}")
            else:
                print(f"    -> [+] Accepted into queue! Redirected to: {redirect_target}")
        else:
            print(f"    -> [!] Error! Form rejected. Status code: {response.status_code}")
            
            # Save the rejected HTML to a file so we can inspect it manually if needed
            with open("error_debug.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("       [DEBUG] Saved the rejected page to 'error_debug.html'.")
            
            # Try to automatically extract Django's error message
            errors = re.findall(r'class="errorlist">.*?<li>(.*?)</li>', response.text, re.DOTALL)
            if errors:
                # Clean up any inner HTML tags
                clean_err = re.sub(r'<[^>]+>', '', errors[0]).strip()
                print(f"       [REASON]: {clean_err}")
            else:
                print("       [REASON]: Could not auto-parse error. Please open 'error_debug.html' in your web browser to see what DMOJ is complaining about.")
            
            # Stop the script on the first error so we can fix it
            break
            
        time.sleep(0.5)


LOG_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../dmoj/dmoj_docker/dmoj/repo/testing/test_results.csv'))

if os.path.exists(LOG_FILE_PATH):
    try:
        os.remove(LOG_FILE_PATH)
        print(f"[+] Old log file deleted: {LOG_FILE_PATH}")
    except OSError as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    run_test()