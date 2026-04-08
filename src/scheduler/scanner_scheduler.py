"""
Scanner Scheduler
Runs the accumulation scanner at a specific time on weekdays
"""

import logging
from datetime import datetime, time
from typing import Callable, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
import pytz

logger = logging.getLogger(__name__)


def is_market_open(config: dict) -> bool:
    """
    Check if current time is within market hours
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if market is open, False otherwise
    """
    scheduler_config = config.get('scheduler', {})
    
    tz = pytz.timezone(scheduler_config.get('timezone', 'Asia/Kolkata'))
    now = datetime.now(tz)
    
    market_open_hour = scheduler_config.get('market_open_hour', 9)
    market_open_minute = scheduler_config.get('market_open_minute', 15)
    market_close_hour = scheduler_config.get('market_close_hour', 15)
    market_close_minute = scheduler_config.get('market_close_minute', 30)
    run_days = scheduler_config.get('run_days', [1, 2, 3, 4, 5])
    
    current_time = now.time()
    current_day = now.weekday()
    
    open_time = time(market_open_hour, market_open_minute)
    close_time = time(market_close_hour, market_close_minute)
    
    is_weekday = current_day in run_days
    is_market_hours = open_time <= current_time <= close_time
    
    return is_weekday and is_market_hours


class ScannerScheduler:
    """
    Scheduler for running the accumulation scanner hourly during market hours
    Also runs an immediate scan on deploy
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.scheduler_config = config.get('scheduler', {})
        
        self.timezone = self.scheduler_config.get('timezone', 'Asia/Kolkata')
        
        self.scan_interval_minutes = self.scheduler_config.get('scan_interval_minutes', 15)
        self.scan_on_deploy = self.scheduler_config.get('scan_on_deploy', True)
        
        self.run_days = self.scheduler_config.get('run_days', [1, 2, 3, 4, 5])
        
        executors = {
            'default': ThreadPoolExecutor(max_workers=2)
        }
        
        self.scheduler = BackgroundScheduler(
            executors=executors,
            timezone=self.timezone
        )
        
        self.job = None
        self.has_run_initial = False
        
    def add_job(self, func: Callable, job_id: str = 'scanner_job') -> None:
        """
        Add the scanner job to the scheduler - runs every 15 minutes during market hours
        """
        from apscheduler.triggers.interval import IntervalTrigger
        
        trigger = IntervalTrigger(
            minutes=self.scan_interval_minutes,
            timezone=self.timezone
        )
        
        self.job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            name=f'Accumulation Scanner (Every {self.scan_interval_minutes}min during market hours)',
            replace_existing=True
        )
        
        logger.info(f"Scanner job scheduled: every {self.scan_interval_minutes} minute(s)")
        
    def should_run_scan(self) -> bool:
        """
        Check if scan should run based on market hours
        
        Returns:
            True if scan should run, False otherwise
        """
        return is_market_open(self.config)
        
    def start(self, run_immediate: bool = True) -> None:
        """
        Start the scheduler
        
        Args:
            run_immediate: If True, run scan immediately on deploy
        """
        if not self.scheduler.running:
            self.scheduler.start()
            
            if run_immediate and self.scan_on_deploy and not self.has_run_initial:
                logger.info("Running immediate scan on deploy...")
                from main import run_scan, setup_logging
                
                logger_obj = setup_logging(self.config)
                try:
                    run_scan(self.config, logger_obj)
                    self.has_run_initial = True
                except Exception as e:
                    logger.error(f"Immediate scan failed: {e}")
            
            logger.info(f"Scheduler started - scanning every {self.scan_interval_minutes}min during market hours")
            
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
            'scan_interval_minutes': self.scan_interval_minutes,
            'scan_on_deploy': self.scan_on_deploy,
            'run_days': self.run_days,
            'market_open': is_market_open(self.config)
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
