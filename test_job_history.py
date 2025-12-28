"""
Test script to verify job history tracking functionality
"""
from job_history import JobHistory
from datetime import datetime, timedelta
import os
import json

def test_job_history():
    # Use a test file
    test_file = "test_job_history.json"
    
    # Clean up any existing test file
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("=" * 60)
    print("Testing Job History Tracker")
    print("=" * 60)
    
    # Test 1: Initialize tracker
    print("\n1. Initializing job history tracker...")
    history = JobHistory(history_file=test_file, retention_days=7)
    print(f"   ✓ Created tracker with {history.retention_days} days retention")
    
    # Test 2: Mark jobs as sent
    print("\n2. Marking jobs as sent...")
    test_jobs = [
        "company1-job1",
        "company2-job2",
        "company3-job3"
    ]
    
    for job_id in test_jobs:
        history.mark_as_sent(job_id)
        print(f"   ✓ Marked as sent: {job_id}")
    
    # Test 3: Check if jobs are tracked
    print("\n3. Checking if jobs are tracked...")
    for job_id in test_jobs:
        is_sent = history.is_sent(job_id)
        print(f"   {'✓' if is_sent else '✗'} Job {job_id}: {'Already sent' if is_sent else 'Not sent'}")
    
    # Test 4: Check statistics
    print("\n4. Getting statistics...")
    stats = history.get_stats()
    print(f"   Total jobs tracked: {stats['total_jobs']}")
    print(f"   Newest entry: {stats['newest_entry']}")
    print(f"   Oldest entry: {stats['oldest_entry']}")
    
    # Test 5: Test with old entry
    print("\n5. Testing cleanup of old entries...")
    # Manually add an old entry
    old_date = (datetime.now() - timedelta(days=10)).isoformat()
    history.history["old-company-old-job"] = old_date
    history._save_history()
    print(f"   ✓ Added old job entry (10 days ago)")
    
    # Run cleanup
    removed = history.cleanup_old_entries()
    print(f"   ✓ Cleaned up {removed} old entries")
    
    # Verify old entry was removed
    is_old_present = history.is_sent("old-company-old-job")
    print(f"   {'✗ Old entry still present!' if is_old_present else '✓ Old entry removed successfully'}")
    
    # Test 6: Verify persistence
    print("\n6. Testing persistence...")
    history2 = JobHistory(history_file=test_file, retention_days=7)
    still_tracked = all(history2.is_sent(job_id) for job_id in test_jobs)
    print(f"   {'✓' if still_tracked else '✗'} Jobs persisted across instances")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    
    # Show final file content
    print(f"\nFinal content of {test_file}:")
    with open(test_file, 'r') as f:
        content = json.load(f)
        print(json.dumps(content, indent=2))
    
    # Clean up test file
    print(f"\nCleaning up test file...")
    os.remove(test_file)
    print("✓ Test file removed")

if __name__ == "__main__":
    test_job_history()
