# Streamlit Deployment Notes

This repo has a Streamlit entrypoint:

```text
app.py
```

## Important

Streamlit Community Cloud is suitable for viewing the dashboard, but it is not the reliable place to run an always-on paper-trading loop. The bot writes to a local SQLite database. If the dashboard runs on Streamlit Cloud while the bot runs on your laptop, the cloud app will not see your laptop's database.

For overnight paper trading, run the bot and dashboard on the same machine:

```powershell
.\scripts\start_overnight.ps1
```

Then open:

```text
http://localhost:8501
```

In the morning:

```powershell
.\scripts\status_overnight.ps1
python tools\replay_current_rules.py
```

To stop:

```powershell
.\scripts\stop_overnight.ps1
```

## To Put The Dashboard On Streamlit Cloud

1. Push this folder to a GitHub repo.
2. Go to Streamlit Community Cloud.
3. Create a new app from that repo.
4. Set the main file path to:

```text
app.py
```

5. Add secrets/environment values matching `.env.example`.

Again: this will deploy the dashboard, not a guaranteed always-on bot.

