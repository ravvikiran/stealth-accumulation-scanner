"""
Scanner Scheduler
Runs the accumulation scanner at a specific time on weekdays
"""

import logging
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ScannerScheduler:
    """
    Scheduler for running the accumulation scanner daily at a specific time
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.scheduler_config = config.get('scheduler', {})
        
        # Configure scheduler
        self.timezone = self.scheduler_config.get('timezone', 'Asia/Kolkata')
        
        # Get scan time (default 3:00 PM IST)
        self.scan_hour = self.scheduler_config.get('scan_time_hour', 15)
        self.scan_minute = self.scheduler_config.get('scan_time_minute', 0)
        
        # Run days: Monday=0, Tuesday=1, ..., Friday=4
        self.run_days = self.scheduler_config.get('run_days', [1, 2, 3, 4, 5])
        
        # Configure executors
        executors = {
            'default': ThreadPoolExecutor(max_workers=2)
        }
        
        # Create scheduler
        self.scheduler = BackgroundScheduler(
            executors=executors,
            timezone=self.timezone
        )
        
        self.job = None
        
    def add_job(self, func: Callable, job_id: str = 'scanner_job') -> None:
        """
        Add the scanner job to the scheduler
        
        Args:
            func: Function to run
            job_id: Unique job identifier
        """
        # Use CronTrigger for specific time on specific days
        trigger = CronTrigger(
            hour=self.scan_hour,
            minute=self.scan_minute,
            day_of_week=self.run_days,
            timezone=self.timezone
        )
        
        self.job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Accumulation Scanner (Daily at {self.scan_hour}:{self.scan_minute:02d} IST)',
            replace_existing=True
        )
        
        logger.info(f"Scanner job scheduled: {self.scan_hour}:{self.scan_minute:02d} IST on days {self.run_days}")
        
    def start(self) -> None:
        """
        Start the scheduler
        """
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info(f"Scheduler started - running at {self.scan_hour}:{self.scan_minute:02d} IST on Mon-Fri")
            
    def stop(self) -> None:
        """
        Stop the scheduler
        """
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
            
    def get_next_run(self) -> Optional[datetime]:
        """
        Get the next scheduled run time
        
        Returns:
            Next run datetime or None
        """
        if self.job:
            return self.job.next_run_time
        return None
    
    def get_status(self) -> dict:
        """
        Get scheduler status
        
        Returns:
            Status dictionary
        """
        return {
            'running': self.scheduler.running,
            'next_run': self.get_next_run(),
            'job_id': self.job.id if self.job else None,
            'scan_time': f'{self.scan_hour}:{self.scan_minute:02d}',
            'run_days': self.run_days
        }
    
    def add_monitor_job(self, func: Callable, job_id: str = 'monitor_job') -> None:
        """
        Add a signal monitoring job to the scheduler
        
        Args:
            func: Function to run for monitoring
            job_id: Unique job identifier
        """
        # Get monitoring interval from config
        sie_config = self.config.get('signal_intelligence', {})
        monitor_interval = sie_config.get('monitoring', {}).get('check_interval_minutes', 15)
        
        from apscheduler.triggers.interval import IntervalTrigger
        trigger = IntervalTrigger(
            minutes=monitor_interval,
            timezone=self.timezone
        )
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name='Signal Monitor (Check active signals)',
            replace_existing=True
        )
        
        logger.info(f"Signal monitoring job scheduled: every {monitor_interval} minutes")


def create_scheduler(config: dict) -> ScannerScheduler:
    """
    Factory function to create a scheduler
    
    Args:
        config: Configuration dictionary
        
    Returns:
        ScannerScheduler instance
    """
    return ScannerScheduler(config)


# CronTrigger helper for manual scheduling
def create_cron_trigger(hour: int = 15, minute: int = 0, day_of_week: str = 'mon-fri'):
    """
    Create a CronTrigger for specific time and days
    
    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)
        day_of_week: Day of week (e.g., 'mon-fri', '0-4')
        
    Returns:
        CronTrigger instance
    """
    return CronTrigger(
        hour=hour,
        minute=minute,
        day_of_week=day_of_week,
        timezone='Asia/Kolkata'
    )
