"""
Test Redis Streams Basic Operations - Phase 1, Task 1.3
========================================================

This test validates that our async Redis setup supports all required
Streams operations before we build the actual streaming infrastructure.

Tests:
- Async connection to Redis
- XADD (producer writes messages)
- XGROUP CREATE (consumer group creation)
- XREADGROUP (consumer reads messages)
- XACK (consumer acknowledges messages)
- XPENDING (check unprocessed messages)

Date: November 8, 2025
Phase: 1 - Foundation
"""

import asyncio
import redis.asyncio as redis
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_redis_streams_producer_consumer():
    """
    Test complete producer-consumer flow with Redis Streams.
    
    This simulates:
    - Subfinder (producer) writing subdomains to stream
    - DNSx (consumer) reading and processing subdomains
    """
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    try:
        # Test connection
        await r.ping()
        print("✅ Redis connection successful")
        
        # Test stream name
        stream_key = "test_stream:phase1"
        consumer_group = "test_consumers"
        consumer_name = "test_consumer_1"
        
        # Clean up any existing test data
        await r.delete(stream_key)
        
        # ============================================================
        # PRODUCER: Write messages to stream (like Subfinder)
        # ============================================================
        print("\n📤 PRODUCER: Writing messages to stream...")
        
        test_messages = [
            {
                "subdomain": f"test{i}.example.com",
                "parent_domain": "example.com",
                "source": "crtsh",
                "discovered_at": datetime.utcnow().isoformat(),
                "asset_id": "test-asset-123",
                "scan_job_id": "test-scan-456"
            }
            for i in range(10)
        ]
        
        message_ids = []
        for msg in test_messages:
            msg_id = await r.xadd(stream_key, msg)
            message_ids.append(msg_id)
        
        print(f"✅ Wrote {len(test_messages)} messages to stream")
        
        # Verify stream length
        stream_len = await r.xlen(stream_key)
        assert stream_len == len(test_messages), f"Expected {len(test_messages)} messages, got {stream_len}"
        print(f"✅ Stream length verified: {stream_len} messages")
        
        # ============================================================
        # CONSUMER SETUP: Create consumer group
        # ============================================================
        print("\n👥 CONSUMER SETUP: Creating consumer group...")
        
        try:
            await r.xgroup_create(stream_key, consumer_group, id='0', mkstream=True)
            print(f"✅ Consumer group '{consumer_group}' created")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"⚠️  Consumer group already exists (OK)")
            else:
                raise
        
        # ============================================================
        # CONSUMER: Read messages from stream (like DNSx)
        # ============================================================
        print(f"\n📥 CONSUMER: Reading messages as '{consumer_name}'...")
        
        consumed_messages = []
        acked_count = 0
        
        # Read in batches (like real DNSx would)
        batch_size = 5
        total_read = 0
        
        while total_read < len(test_messages):
            # XREADGROUP: Read batch of messages
            streams = await r.xreadgroup(
                groupname=consumer_group,
                consumername=consumer_name,
                streams={stream_key: '>'},  # '>' means undelivered messages
                count=batch_size,
                block=1000  # Wait 1 second if no messages
            )
            
            if not streams:
                print("⚠️  No messages available")
                break
            
            # Process messages
            for stream_name, messages in streams:
                for message_id, message_data in messages:
                    consumed_messages.append(message_data)
                    total_read += 1
                    
                    # ACK the message (tell Redis we processed it)
                    await r.xack(stream_key, consumer_group, message_id)
                    acked_count += 1
            
            print(f"  Batch: Read {len(messages)} messages (total: {total_read}/{len(test_messages)})")
        
        print(f"✅ Consumed {len(consumed_messages)} messages")
        print(f"✅ ACK'd {acked_count} messages")
        
        # ============================================================
        # VALIDATION: Check all messages processed
        # ============================================================
        print("\n🔍 VALIDATION: Checking stream state...")
        
        # Check XPENDING - should be 0 (all messages ACK'd)
        pending_info = await r.xpending(stream_key, consumer_group)
        pending_count = pending_info['pending']
        
        assert pending_count == 0, f"Expected 0 pending messages, got {pending_count}"
        print(f"✅ XPENDING = {pending_count} (all messages acknowledged)")
        
        # Verify we consumed all messages
        assert len(consumed_messages) == len(test_messages), \
            f"Expected {len(test_messages)} messages, consumed {len(consumed_messages)}"
        print(f"✅ All {len(consumed_messages)} messages processed")
        
        # Verify message content
        for i, msg in enumerate(consumed_messages):
            assert msg['subdomain'] == f"test{i}.example.com", \
                f"Message {i} subdomain mismatch"
            assert msg['parent_domain'] == "example.com"
            assert msg['source'] == "crtsh"
        
        print("✅ Message content validation passed")
        
        # ============================================================
        # SUCCESS
        # ============================================================
        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        print(f"✅ Producer: Wrote {len(test_messages)} messages")
        print(f"✅ Consumer: Read {len(consumed_messages)} messages")
        print(f"✅ ACK'd: {acked_count} messages")
        print(f"✅ Pending: {pending_count} messages")
        print("\nRedis Streams infrastructure is READY for streaming pipeline! 🚀")
        print("="*70)
        
    finally:
        # Cleanup
        await r.delete(stream_key)
        await r.close()


@pytest.mark.asyncio
async def test_redis_streams_completion_marker():
    """
    Test completion marker pattern (how DNSx knows Subfinder is done).
    """
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    try:
        stream_key = "test_stream:completion"
        completion_key = f"{stream_key}:complete"
        
        # Clean up
        await r.delete(stream_key, completion_key)
        
        # Producer writes some messages
        await r.xadd(stream_key, {"msg": "1"})
        await r.xadd(stream_key, {"msg": "2"})
        
        # Check if producer is complete (should be False)
        exists = await r.exists(completion_key)
        assert exists == 0, "Completion marker shouldn't exist yet"
        print("✅ Completion marker correctly absent during production")
        
        # Producer finishes and sets completion marker
        await r.set(completion_key, "1", ex=3600)  # TTL: 1 hour
        
        # Consumer checks completion
        exists = await r.exists(completion_key)
        assert exists == 1, "Completion marker should exist"
        print("✅ Completion marker correctly set after production")
        
        # Cleanup
        await r.delete(stream_key, completion_key)
        
    finally:
        await r.close()


if __name__ == "__main__":
    """
    Run tests directly (without pytest).
    Usage: python test_redis_streams_basic.py
    """
    print("Starting Redis Streams Basic Tests...")
    print("="*70 + "\n")
    
    # Run main test
    asyncio.run(test_redis_streams_producer_consumer())
    
    print("\n")
    
    # Run completion marker test
    asyncio.run(test_redis_streams_completion_marker())
    
    print("\n" + "="*70)
    print("✅ All Redis Streams tests completed successfully!")
    print("="*70)
