import time
import csv
import os
from django.conf import settings

LOG_FILE = os.path.join(settings.BASE_DIR, 'sae_stress_test.csv')

def log_step(sub_id, step_name, duration):
    """
    Logs individual pipeline steps.
    step_name: e.g., 'SAE_ANALYSIS' or 'DB_UPDATE'
    """
    file_exists = os.path.exists(LOG_FILE)
    
    with open(LOG_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            # Write header if file is newly created
            writer.writerow(['Submission_ID', 'Step', 'Duration_sec', 'Worker_PID'])
        
        writer.writerow([sub_id, step_name, f"{duration:.4f}", os.getpid()])
        
    print(f"[SAE-Bench] Sub {sub_id} | {step_name}: {duration:.4f}s")