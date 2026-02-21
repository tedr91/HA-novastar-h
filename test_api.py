"""Test script to debug Novastar API connection."""

import asyncio
import aiohttp
import hashlib
import base64
import time
import json

# ============ CONFIGURE THESE ============
HOST = "192.168.21.99"  # Your H2's IP address
PORT = 8000
PROJECT_ID = "NDdi"
SECRET_KEY = "MmZjZWVm"
ENCRYPTION = False
# =========================================


def get_timestamp() -> str:
    return str(int(time.time() * 1000))


def generate_signature(timestamp: str, project_id: str) -> str:
    """Generate signature for unencrypted request."""
    message = f"{timestamp}{project_id}"
    md5_hash = hashlib.md5(message.encode()).hexdigest()
    return base64.b64encode(md5_hash.encode()).decode()


async def test_request(session, description: str, url: str, data: dict):
    """Test a single request and print results."""
    print(f"\n--- {description} ---")
    print(f"Request: {json.dumps(data)}")
    try:
        async with session.post(url, json=data) as response:
            text = await response.text()
            print(f"Status: {response.status}")
            print(f"Response: {text[:200]}...")  # Truncate long responses
            return text
    except Exception as e:
        print(f"Error: {e}")
        return None


async def test_connection():
    print(f"\n=== Testing Novastar API Connection ===")
    print(f"Host: {HOST}:{PORT}")
    
    url = f"http://{HOST}:{PORT}/open/api/device/readDetail"
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        
        # Test with authentication (known working)
        timestamp = get_timestamp()
        signature = generate_signature(timestamp, PROJECT_ID)
        await test_request(session, "With auth: body={deviceId:0}", url, {
            "body": {"deviceId": 0},
            "sign": signature,
            "pId": PROJECT_ID,
            "timeStamp": timestamp,
        })
        
        # Test without authentication (for discovery)
        timestamp = get_timestamp()
        signature = generate_signature(timestamp, "")  # Empty project ID
        await test_request(session, "No auth: body={deviceId:0}, empty pId", url, {
            "body": {"deviceId": 0},
            "sign": signature,
            "pId": "",
            "timeStamp": timestamp,
        })
        
        # Test with minimal request (no auth fields)
        await test_request(session, "Minimal: just body={deviceId:0}", url, {
            "body": {"deviceId": 0},
        })

    print("\n=== Test Complete ===\n")


if __name__ == "__main__":
    asyncio.run(test_connection())
