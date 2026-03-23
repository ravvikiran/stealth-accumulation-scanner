"""
Scanner Scheduler
Runs the accumulation scanner every 15 minutes during market hours
"""

import logging
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ScannerScheduler:
    """
    Scheduler for running the accumulation scanner every 15 minutes
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.scheduler_config = config.get('scheduler', {})
        
        # Configure scheduler
        self.timezone = self.scheduler_config.get('timezone', 'Asia/Kolkata')
        
        # Get interval in minutes
        self.interval_minutes = self.scheduler_config.get('interval_minutes', 15)
        
        # Market hours
        self.market_open_hour = self.scheduler_config.get('market_open_hour', 9)
        self.market_open_minute = self.scheduler_config.get('market_open_minute', 15)
        self.market_close_hour = self.scheduler_config.get('market_close_hour', 15)
        self.market_close_minute = self.scheduler_config.get('market_close_minute', 30)
        
        # Configure executors
        executors = {
            'default': ThreadPoolExecutor(max_workers=1)
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
        # Use interval trigger for every 15 minutes
        trigger = IntervalTrigger(
            minutes=self.interval_minutes,
            timezone=self.timezone
        )
        
        self.job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name='Accumulation Scanner (Every 15 min)',
            replace_existing=True
        )
        
        logger.info(f"Scanner job scheduled: every {self.interval_minutes} minutes during market hours")
        
    def start(self) -> None:
        """
        Start the scheduler
        """
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started - running every 15 minutes")
            
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
            'interval_minutes': self.interval_minutes
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


# Interval trigger helper for manual scheduling
def create_interval_trigger(minutes: int = 15) -> IntervalTrigger:
    """
    Create an interval trigger
    
    Args:
        minutes: Interval in minutes
        
    Returns:
        IntervalTrigger instance
    """
    return IntervalTrigger(
        minutes=minutes,
        timezone='Asia/Kolkata'
    )
