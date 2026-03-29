# Auth Testing Playbook for BuddyBot

## Step 1: Test Backend API

```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Login
TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" -H "Content-Type: application/json" -d '{"email":"parent@test.com","password":"secure123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# Auth me
curl -s "$API_URL/api/auth/me" -H "Authorization: Bearer $TOKEN"

# Verify password
curl -s -X POST "$API_URL/api/auth/verify-password" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"password":"secure123"}'

# Protected dashboard
curl -s "$API_URL/api/parent/dashboard" -H "Authorization: Bearer $TOKEN"
```

## Step 2: Browser Testing

```python
# Set auth token in localStorage
await page.evaluate("localStorage.setItem('buddybot_token', 'YOUR_TOKEN')")
await page.goto("https://your-app.com/parent")
```

## Checklist
- [ ] Registration creates user + child profile
- [ ] Login returns JWT token
- [ ] /api/auth/me returns user with children
- [ ] Password verification works (correct + incorrect)
- [ ] Parent dashboard requires authentication
- [ ] Password gate shows on parent dashboard visit
- [ ] Google OAuth callback exchanges session_id for JWT
- [ ] Logout clears token
