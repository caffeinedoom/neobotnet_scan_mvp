#!/usr/bin/env python3
"""
Redis Health Check Script for NeoBot-Net v2
Diagnoses Redis connection issues across different environments
"""

import asyncio
import os
import sys
import time
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import redis.asyncio as redis
except ImportError:
    import redis

from app.core.config import settings

async def test_redis_connection() -> Dict[str, Any]:
    """Test Redis connection with detailed diagnostics."""
    
    print("🔍 Redis Connection Diagnostics")
    print("=" * 50)
    
    # Environment information
    print(f"📊 Environment: {settings.environment}")
    print(f"🌐 Cloud Environment: {settings.is_cloud_environment}")
    print(f"🔗 Redis Host: {settings.redis_host}")
    print(f"🚪 Redis Port: {settings.redis_port}")
    print(f"🔐 Auth Token: {'Yes' if settings.redis_auth_token else 'No'}")
    print(f"🔒 SSL Enabled: {settings.redis_ssl}")
    
    results = {
        "environment": settings.environment,
        "is_cloud": settings.is_cloud_environment,
        "host": settings.redis_host,
        "port": settings.redis_port,
        "connection_successful": False,
        "ping_successful": False,
        "write_test_successful": False,
        "read_test_successful": False,
        "error_message": None,
        "latency_ms": None,
    }
    
    try:
        print("\n🔌 Attempting Redis connection...")
        
        # Get connection configuration
        redis_config = settings.redis_connection_kwargs
        print(f"🛠️  Connection config: {redis_config}")
        
        # Start timing
        start_time = time.time()
        
        # Create Redis client
        redis_client = redis.Redis(**redis_config)
        results["connection_successful"] = True
        print("✅ Redis client created successfully")
        
        # Test ping
        print("🏓 Testing ping...")
        await redis_client.ping()
        results["ping_successful"] = True
        ping_time = time.time()
        results["latency_ms"] = round((ping_time - start_time) * 1000, 2)
        print(f"✅ Ping successful (latency: {results['latency_ms']}ms)")
        
        # Test write operation
        print("✍️  Testing write operation...")
        test_key = f"health_check_{int(time.time())}"
        await redis_client.set(test_key, "test_value", ex=60)  # Expire in 60 seconds
        results["write_test_successful"] = True
        print(f"✅ Write test successful (key: {test_key})")
        
        # Test read operation  
        print("📖 Testing read operation...")
        value = await redis_client.get(test_key)
        if value == "test_value":
            results["read_test_successful"] = True
            print("✅ Read test successful")
        else:
            print(f"❌ Read test failed: expected 'test_value', got '{value}'")
        
        # Cleanup test key
        await redis_client.delete(test_key)
        print("🧹 Cleanup completed")
        
        # Test caching functionality (simulate auth cache)
        print("🔐 Testing authentication cache simulation...")
        cache_key = "user:test_user_123"
        cache_data = {
            "id": "test_user_123",
            "email": "test@example.com",
            "full_name": "Test User"
        }
        
        # Set cache with JSON serialization
        import json
        await redis_client.setex(cache_key, 300, json.dumps(cache_data))
        
        # Get cache
        cached_json = await redis_client.get(cache_key)
        if cached_json:
            cached_data = json.loads(cached_json)
            if cached_data["id"] == "test_user_123":
                print("✅ Authentication cache simulation successful")
                results["auth_cache_test"] = True
            else:
                print("❌ Authentication cache simulation failed: data mismatch")
                results["auth_cache_test"] = False
        else:
            print("❌ Authentication cache simulation failed: no data returned")
            results["auth_cache_test"] = False
            
        # Cleanup
        await redis_client.delete(cache_key)
        
        # Close connection
        await redis_client.aclose()
        print("🔌 Connection closed")
        
    except Exception as e:
        results["error_message"] = str(e)
        print(f"❌ Redis connection failed: {str(e)}")
        
        # Additional diagnostics for common issues
        if "Connection refused" in str(e):
            print("\n🔍 Diagnosis: Connection Refused")
            print("   - Check if Redis server is running")
            print("   - Verify host and port configuration")
            print("   - Check network connectivity")
            
        elif "timeout" in str(e).lower():
            print("\n🔍 Diagnosis: Connection Timeout")
            print("   - Check security group rules (ECS → Redis)")
            print("   - Verify Redis is in correct subnet")
            print("   - Check VPC routing configuration")
            
        elif "auth" in str(e).lower() or "authentication" in str(e).lower():
            print("\n🔍 Diagnosis: Authentication Error")
            print("   - Check if AUTH token is required")
            print("   - Verify AUTH token configuration")
            print("   - Check ElastiCache AUTH settings")
    
    return results

async def main():
    """Main execution function."""
    
    print("🚀 NeoBot-Net v2 Redis Health Check")
    print("Ensuring Redis connectivity across environments")
    print()
    
    # Run diagnostics
    results = await test_redis_connection()
    
    # Summary
    print("\n📋 HEALTH CHECK SUMMARY")
    print("=" * 50)
    
    success_count = sum([
        results.get("connection_successful", False),
        results.get("ping_successful", False),
        results.get("write_test_successful", False),
        results.get("read_test_successful", False),
        results.get("auth_cache_test", False)
    ])
    
    total_tests = 5
    success_rate = (success_count / total_tests) * 100
    
    if success_rate == 100:
        print("🎉 ALL TESTS PASSED - Redis is healthy!")
        print(f"   Latency: {results.get('latency_ms', 'N/A')}ms")
    elif success_rate >= 80:
        print("⚠️  MOSTLY WORKING - Some issues detected")
        print(f"   Success Rate: {success_rate:.1f}%")
    else:
        print("❌ CRITICAL ISSUES - Redis not functioning properly")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Error: {results.get('error_message', 'Unknown')}")
    
    # Environment-specific recommendations
    print("\n💡 Environment-Specific Recommendations:")
    
    if settings.environment in ["local-dev", "dev"]:
        print("   LOCAL DEVELOPMENT:")
        print("   - Ensure Redis is running: docker-compose up redis")
        print("   - Check host networking: network_mode: host")
        print("   - Verify Redis Commander: http://localhost:8081")
        
    elif settings.is_cloud_environment:
        print("   CLOUD ENVIRONMENT:")
        print("   - Verify ECS task can reach ElastiCache")
        print("   - Check security group rules")
        print("   - Confirm VPC subnet routing")
        print("   - Review ElastiCache cluster status")
    
    # Return appropriate exit code
    sys.exit(0 if success_rate == 100 else 1)

if __name__ == "__main__":
    asyncio.run(main())
