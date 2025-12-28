"""
Job History Tracker - Prevents sending duplicate jobs within a time window
"""
import json
import os
from datetime import datetime, timedelta
import logging

class JobHistory:
    def __init__(self, history_file="sent_jobs_history.json", retention_days=7):
        """
        Initialize job history tracker
        
        Args:
            history_file: Path to JSON file storing job history
            retention_days: Number of days to keep job records (default: 7)
        """
        self.history_file = history_file
        self.retention_days = retention_days
        self.history = self._load_history()
        
    def _load_history(self):
        """Load job history from JSON file"""
        if not os.path.exists(self.history_file):
            logging.info(f"No existing job history found, creating new file: {self.history_file}")
            return {}
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            logging.info(f"Loaded {len(history)} jobs from history")
            return history
        except Exception as e:
            logging.error(f"Error loading job history: {e}")
            return {}
    
    def _save_history(self):
        """Save job history to JSON file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            logging.debug(f"Saved {len(self.history)} jobs to history")
        except Exception as e:
            logging.error(f"Error saving job history: {e}")
    
    def cleanup_old_entries(self):
        """Remove job entries older than retention_days"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        cutoff_timestamp = cutoff_date.isoformat()
        
        initial_count = len(self.history)
        self.history = {
            job_id: timestamp 
            for job_id, timestamp in self.history.items() 
            if timestamp > cutoff_timestamp
        }
        
        removed_count = initial_count - len(self.history)
        if removed_count > 0:
            logging.info(f"Cleaned up {removed_count} old job entries (older than {self.retention_days} days)")
            self._save_history()
        
        return removed_count
    
    def is_sent(self, job_id):
        """
        Check if a job has already been sent
        
        Args:
            job_id: Unique identifier for the job
            
        Returns:
            bool: True if job was already sent, False otherwise
        """
        return job_id in self.history
    
    def mark_as_sent(self, job_id):
        """
        Mark a job as sent with current timestamp
        
        Args:
            job_id: Unique identifier for the job
        """
        self.history[job_id] = datetime.now().isoformat()
        self._save_history()
        logging.debug(f"Marked job as sent: {job_id}")
    
    def get_stats(self):
        """Get statistics about job history"""
        if not self.history:
            return {
                "total_jobs": 0,
                "oldest_entry": None,
                "newest_entry": None
            }
        
        timestamps = list(self.history.values())
        return {
            "total_jobs": len(self.history),
            "oldest_entry": min(timestamps),
            "newest_entry": max(timestamps)
        }
