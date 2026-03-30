# Integration Script for Crypto Scanner

Use this script to add Telegram bot + Scheduler integration to your crypto scanner project.

## Prerequisites
- Your crypto project should have a similar structure to the stock scanner
- It should already have:
  - `main.py` - main entry point
  - `config.yaml` - configuration file
  - `src/scheduler/scanner_scheduler.py` - existing scheduler (or create it)
  - `src/notifications/telegram_bot.py` - existing telegram bot (or create it)
  - `requirements.txt` - dependencies

---

## Step 1: Add yfinance to requirements.txt

**File: `requirements.txt`**

Add this line in the Data Handling section:
```
yfinance>=0.2.0
```

---

## Step 2: Fix logs directory creation

**File: `main.py`**

Find the `setup_logging` function and add directory creation before the FileHandler:

```python
def setup_logging(config: dict):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    
    level = getattr(logging, log_config.get('level', 'INFO'))
    log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create logs directory if it doesn't exist
    log_file = log_config.get('file', 'logs/scanner.log')
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )
    
    return logging.getLogger(__name__)
```

Make sure you have this import at the top:
```python
from pathlib import Path
```

---

## Step 3: Update config.yaml scheduler section

**File: `config.yaml`**

Replace the scheduler section with:
```yaml
scheduler:
  timezone: "Asia/Kolkata"

  # Run daily at 3:00 PM IST (single scan per day)
  scan_time_hour: 15
  scan_time_minute: 0

  run_days: [1, 2, 3, 4, 5]  # Monday to Friday

  # Market hours (for crypto, you might adjust these)
  market_open_hour: 9
  market_open_minute: 15
  market_close_hour: 15
  market_close_minute: 30
```

---

## Step 4: Update scanner_scheduler.py to use CronTrigger

**File: `src/scheduler/scanner_scheduler.py`**

Replace the entire file with:
```python
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
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info(f"Scheduler started - running at {self.scan_hour}:{self.scan_minute:02d} IST on Mon-Fri")
            
    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
            
    def get_next_run(self) -> Optional[datetime]:
        if self.job:
            return self.job.next_run_time
        return None
    
    def get_status(self) -> dict:
        return {
            'running': self.scheduler.running,
            'next_run': self.get_next_run(),
            'job_id': self.job.id if self.job else None,
            'scan_time': f'{self.scan_hour}:{self.scan_minute:02d}',
            'run_days': self.run_days
        }
    
    def add_monitor_job(self, func: Callable, job_id: str = 'monitor_job') -> None:
        """Add a signal monitoring job"""
        from apscheduler.triggers.interval import IntervalTrigger
        
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
            name='Signal Monitor',
            replace_existing=True
        )
        
        logger.info(f"Signal monitoring job scheduled: every {monitor_interval} minutes")


def create_scheduler(config: dict) -> ScannerScheduler:
    return ScannerScheduler(config)
```

---

## Step 5: Update main.py to integrate scheduler + telegram bot

**File: `main.py`**

1. Add `threading` import:
```python
import threading
```

2. Replace the `run_scheduled` function with:
```python
def run_scheduled(config: dict, logger):
    """
    Run the scanner with scheduler and Telegram bot (both running together)
    """
    logger.info("Initializing scheduler and Telegram bot...")
    
    # Create scheduler
    scheduler = ScannerScheduler(config)
    
    # Add the scan job
    def scan_job():
        run_scan(config, logger)
    
    scheduler.add_job(scan_job)
    
    # Add signal monitoring job if SIE is enabled
    sie_config = config.get('signal_intelligence', {})
    if sie_config.get('enabled', True):
        def monitor_job():
            from src.intelligence.sie_orchestrator import SIEOrchestrator
            from src.notifications.telegram_bot import TelegramBot
            from src.data.data_fetcher import NSEDataFetcher
            
            fetcher = NSEDataFetcher(config)
            bot = TelegramBot(config)
            sie = SIEOrchestrator(config, bot)
            sie.check_and_update_signals(fetcher)
        
        scheduler.add_monitor_job(monitor_job)
    
    # Start scheduler
    scheduler.start()
    
    logger.info(f"Scheduler running. Next scan: {scheduler.get_next_run()}")
    
    # Start Telegram bot in polling mode (in a separate thread)
    bot = TelegramBot(config)
    bot_thread = None
    
    if bot.is_configured():
        logger.info("Starting Telegram bot in polling mode...")
        bot_thread = threading.Thread(target=bot.start_polling, daemon=True)
        bot_thread.start()
    else:
        logger.warning("Telegram bot not configured - polling not started")
    
    logger.info("System running. Scanner at 3 PM Mon-Fri, bot responding to commands.")
    logger.info("Press Ctrl+C to stop")
    
    try:
        import time
        while True:
            time.sleep(60)
            logger.debug(f"Next scan: {scheduler.get_next_run()}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        scheduler.stop()
```

3. Update the argument parser to indicate combined functionality:
```python
parser.add_argument(
    '--schedule',
    action='store_true',
    help='Run with scheduler (daily at 3 PM Mon-Fri) + Telegram bot'
)
```

---

## Step 6: Deploy on Railway

Set Start Command:
```
python main.py --schedule
```

---

## What This Does

- **Scheduler**: Runs once daily at 3 PM IST on Monday-Friday
- **Telegram Bot**: Runs in parallel, responding to commands like `/scan`, `/status`, `/help`
- Both run in the same process with a single command
