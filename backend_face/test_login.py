import requests
import json

# Test login endpoint
response = requests.post('http://localhost:8005/api/auth/login', json={
    'username': 'superadmin',
    'password': 'super123',
    'role': 'SuperAdmin'
})
print('Login response:', response.status_code)
if response.status_code == 200:
    print('Login successful:', response.json())
else:
    print('Login failed:', response.text)