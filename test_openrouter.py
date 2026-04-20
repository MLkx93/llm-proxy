#!/usr/bin/env python3
"""
OpenRouter Integration Test Script
==================================
Tests the LLM proxy with OpenRouter as the LLM provider.

Usage:
    python test_openrouter.py

Requirements:
    - Set OPENROUTER_API_KEY in .env file
    - Start the proxy server: uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080 --reload
"""

import os
import sys
import json
import httpx

# Load environment variables from .env
def load_env():
    """Load environment variables from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env()

# Configuration
PROXY_BASE_URL = os.getenv('PROXY_BASE_URL', 'http://localhost:8080')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
MODEL = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-4-5-haiku')

# Test keys from api_keys.yaml
TEST_API_KEY = "dev-local-key-1234"


def test_health():
    """Test health endpoint."""
    print("\n" + "="*60)
    print("TEST: Health Check")
    print("="*60)
    
    try:
        response = httpx.get(f"{PROXY_BASE_URL}/health", timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Health check passed!")
            return True
        else:
            print("❌ Health check failed!")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


def test_openai_endpoint():
    """Test the /v1/chat/completions endpoint with OpenRouter."""
    print("\n" + "="*60)
    print("TEST: OpenAI Endpoint (/v1/chat/completions)")
    print("="*60)
    
    headers = {
        "Authorization": f"Bearer {TEST_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "What is 2+2? Answer in one word."}
        ],
        "max_tokens": 50,
        "temperature": 0.3
    }
    
    print(f"Model: {MODEL}")
    print(f"Prompt: {payload['messages'][0]['content']}")
    
    try:
        response = httpx.post(
            f"{PROXY_BASE_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=60
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse:")
            print(f"  Model: {data.get('model', 'N/A')}")
            content = data.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')
            print(f"  Content: {content}")
            
            usage = data.get('usage', {})
            print(f"  Usage: {usage}")
            
            print("✅ OpenAI endpoint test passed!")
            return True
        else:
            print(f"❌ OpenAI endpoint test failed!")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ OpenAI endpoint test failed: {e}")
        return False


def test_anthropic_endpoint():
    """Test the /v1/messages endpoint with OpenRouter."""
    print("\n" + "="*60)
    print("TEST: Anthropic Endpoint (/v1/messages)")
    print("="*60)
    
    # For /v1/messages, use OpenRouter API key for auth
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "What is 3+3? Answer in one word."}
        ],
        "max_tokens": 50
    }
    
    print(f"Model: {MODEL}")
    print(f"Prompt: {payload['messages'][0]['content']}")
    
    try:
        response = httpx.post(
            f"{PROXY_BASE_URL}/v1/messages",
            json=payload,
            headers=headers,
            timeout=60
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse:")
            print(f"  Type: {data.get('type', 'N/A')}")
            content = data.get('content', [{}])[0].get('text', 'N/A')
            print(f"  Content: {content}")
            
            usage = data.get('usage', {})
            print(f"  Usage: {usage}")
            
            print("✅ Anthropic endpoint test passed!")
            return True
        else:
            print(f"❌ Anthropic endpoint test failed!")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Anthropic endpoint test failed: {e}")
        return False


def test_pii_blocking():
    """Test that PII blocking works."""
    print("\n" + "="*60)
    print("TEST: PII Blocking")
    print("="*60)
    
    headers = {
        "Authorization": f"Bearer {TEST_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "Send results to john.doe@example.com"}
        ],
        "max_tokens": 50
    }
    
    print(f"Prompt: {payload['messages'][0]['content']}")
    
    try:
        response = httpx.post(
            f"{PROXY_BASE_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 400:
            data = response.json()
            print(f"Response: {data}")
            
            error = data.get('error', {})
            if error.get('code') == 'BLOCKED_PII':
                print("✅ PII blocking works correctly!")
                return True
        
        print("❌ PII blocking test failed!")
        print(f"Response: {response.text}")
        return False
    except Exception as e:
        print(f"❌ PII blocking test failed: {e}")
        return False


def test_unauthorized():
    """Test that unauthorized requests are blocked."""
    print("\n" + "="*60)
    print("TEST: Unauthorized Access")
    print("="*60)
    
    headers = {
        "Authorization": "Bearer invalid-key-12345",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 10
    }
    
    try:
        response = httpx.post(
            f"{PROXY_BASE_URL}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 401:
            print("✅ Unauthorized access blocked correctly!")
            return True
        
        print("❌ Unauthorized access test failed!")
        print(f"Response: {response.text}")
        return False
    except Exception as e:
        print(f"❌ Unauthorized access test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("OpenRouter Integration Test Suite")
    print("="*60)
    print(f"Proxy URL: {PROXY_BASE_URL}")
    print(f"Model: {MODEL}")
    
    if not OPENROUTER_API_KEY:
        print("\n❌ ERROR: OPENROUTER_API_KEY not set in .env file")
        sys.exit(1)
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health()))
    results.append(("Unauthorized Access", test_unauthorized()))
    results.append(("PII Blocking", test_pii_blocking()))
    results.append(("OpenAI Endpoint", test_openai_endpoint()))
    results.append(("Anthropic Endpoint", test_anthropic_endpoint()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
