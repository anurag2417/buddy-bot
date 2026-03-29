#!/usr/bin/env python3
"""
Specific test for authentication enforcement
"""

import asyncio
import httpx
import json

BASE_URL = "https://get-restart.preview.emergentagent.com/api"

async def test_auth_enforcement():
    """Test that endpoints properly require authentication"""
    client = httpx.AsyncClient(timeout=30.0)
    
    print("Testing authentication enforcement...")
    
    # Test 1: Chat endpoint without any token
    print("\n1. Testing /chat/send without token:")
    response = await client.post(f"{BASE_URL}/chat/send", json={"text": "test"})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    # Test 2: Chat endpoint with invalid token
    print("\n2. Testing /chat/send with invalid token:")
    headers = {"Authorization": "Bearer invalid_token_here"}
    response = await client.post(f"{BASE_URL}/chat/send", headers=headers, json={"text": "test"})
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    # Test 3: Parent dashboard without token
    print("\n3. Testing /parent/dashboard without token:")
    response = await client.get(f"{BASE_URL}/parent/dashboard")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    # Test 4: Auth me without token
    print("\n4. Testing /auth/me without token:")
    response = await client.get(f"{BASE_URL}/auth/me")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:200]}")
    
    await client.aclose()

if __name__ == "__main__":
    asyncio.run(test_auth_enforcement())