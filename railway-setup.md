# Railway Deployment Settings

To run the scanner with the scheduler on Railway:

1. Go to your project on [Railway.app](https://railway.app)
2. Click on your service (the deployed app)
3. Click the **Settings** tab
4. Scroll to **Start Command** 
5. Set it to: `python main.py --schedule`
6. Click **Deploy** or **Save**

---

**What happens:**
- Scanner runs **daily at 3:00 PM IST** on **Monday to Friday** only
- Telegram bot runs in parallel, responding to commands

---

**Available Commands (via Telegram):**
| Command | Description |
|---------|-------------|
| `/scan` or `/run` | Run a scan immediately |
| `/status` | Check scanner status |
| `/help` | Show help message |

---

**Quick Reference:**
| Command | What it does |
|---------|--------------|
| `python main.py` | Single scan (for testing) |
| `python main.py --schedule` | Scheduler (3 PM Mon-Fri) + Telegram bot |
| `python main.py --test` | Test Telegram connection |
