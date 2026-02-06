#!/usr/bin/env python3
"""
Test script to verify authentication system functionality
"""

import requests
import json
import sys

def test_login(username, password, role):
    """Test login with given credentials"""
    url = "http://localhost:8005/api/auth/login"
    payload = {
        "username": username,
        "password": password,
        "role": role
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Login attempt for {username} ({role}):")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Token: {data.get('access_token', 'N/A')[:20]}...")
            return data.get('access_token')
        else:
            print(f"Failed: {response.text}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def test_analytics_endpoint(token):
    """Test analytics endpoint with authentication"""
    url = "http://localhost:8005/api/analytics/overview"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Analytics test:")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Data: {data}")
        else:
            print(f"Failed: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    print("Testing Face Recognition API Authentication System")
    print("=" * 50)
    
    # Test different user types
    users = [
        ("eagleai", "Eagle@1234", "SuperAdmin"),
        ("admin1", "admin123", "Admin"),
        ("super1", "supervisor123", "Supervisor")
    ]
    
    for username, password, role in users:
        token = test_login(username, password, role)
        if token:
            test_analytics_endpoint(token)
            print("-" * 30)
    
    print("\nTesting public endpoints:")
    print("-" * 30)
    
    # Test public endpoints
    try:
        response = requests.get("http://localhost:8005/api/status")
        print(f"Status endpoint: {response.status_code}")
        if response.status_code == 200:
            print("Status endpoint is working!")
    except Exception as e:
        print(f"Status endpoint error: {e}")

if __name__ == "__main__":
    main()