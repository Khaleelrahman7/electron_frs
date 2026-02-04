import requests
import json

# Test bootstrap endpoint first to create SuperAdmin
print("Testing bootstrap endpoint...")
response = requests.post('http://localhost:8005/api/auth/bootstrap/superadmin', json={
    'username': 'eagleai',
    'password': 'Eagle@1234'
})
print('Bootstrap response:', response.status_code)
if response.status_code == 200:
    print('Bootstrap successful:', response.json())
else:
    print('Bootstrap failed:', response.text)

# Test login endpoint
print("\nTesting login endpoint...")
response = requests.post('http://localhost:8005/api/auth/login', json={
    'username': 'eagleai',
    'password': 'Eagle@1234',
    'role': 'SuperAdmin'
})
print('Login response:', response.status_code)
if response.status_code == 200:
    print('Login successful:', response.json())
else:
    print('Login failed:', response.text)