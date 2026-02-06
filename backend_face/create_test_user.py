#!/usr/bin/env python3
"""
Script to create a test user with a known password to verify authentication system
"""

import bcrypt
import json
import os

def create_test_user():
    """Create a test user with a known password"""
    
    # Create password hash for "test123"
    password = "test123"
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Test user data
    test_user = {
        "testuser": {
            "id": "test-user-123",
            "username": "testuser",
            "role": "Supervisor",
            "created_by": "system",
            "menus": ["dashboard", "analytics", "registration"],
            "camera_limit": 5,
            "assigned_cameras": [],
            "is_active": True,
            "created_at": "2026-02-05T12:00:00+00:00",
            "updated_at": "2026-02-05T12:00:00+00:00",
            "hashed_password": hashed_password
        }
    }
    
    # Read existing users
    users_file = "data/auth/users.json"
    
    try:
        if os.path.exists(users_file):
            with open(users_file, 'r') as f:
                users = json.load(f)
        else:
            users = {}
        
        # Add test user
        users.update(test_user)
        
        # Write back to file
        with open(users_file, 'w') as f:
            json.dump(users, f, indent=2)
        
        print(f"Test user created successfully!")
        print(f"Username: testuser")
        print(f"Password: {password}")
        print(f"Role: Supervisor")
        print(f"Users file updated: {users_file}")
        
        return True
        
    except Exception as e:
        print(f"Error creating test user: {e}")
        return False

if __name__ == "__main__":
    create_test_user()