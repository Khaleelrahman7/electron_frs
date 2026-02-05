
import sys
import os
from pathlib import Path

# Add backend_face to path
sys.path.append(os.path.join(os.getcwd(), 'backend_face'))

from auth.storage import ensure_auth_data_dir, get_users
from auth.users import create_user

def verify_and_setup():
    print("Verifying setup...")
    
    # 1. Ensure directory
    ensure_auth_data_dir()
    print("✓ Auth directory ensured")
    
    # 2. Check users
    users = get_users()
    print(f"Found {len(users)} users")
    
    superadmin_exists = False
    for username, data in users.items():
        if data.get('role') == 'SuperAdmin':
            print(f"✓ SuperAdmin found: {username}")
            superadmin_exists = True
            break
            
    if not superadmin_exists:
        print("Creating default SuperAdmin...")
        try:
            create_user("eagleai", "Eagle@1234", "SuperAdmin", "system")
            print("✓ SuperAdmin 'eagleai' created")
        except Exception as e:
            print(f"Error creating user: {e}")
    
    print("Setup verification complete.")

if __name__ == "__main__":
    verify_and_setup()
