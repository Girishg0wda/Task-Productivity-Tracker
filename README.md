# Task & Productivity Tracker (Django + SQLite)

Simple web app where users can create tasks, update their status, and view productivity summaries.

## Features

- Create tasks (title, description, priority, due date, status)
- Update and delete tasks
- Dashboard with:
  - Total tasks
  - Completed, pending, overdue tasks
  - Completion percentage
- SQLite storage
- Search & filter by text, status, priority, due date
- Productivity charts (Chart.js):
  - Tasks completed per day (last 7 days)
  - Task distribution by priority
- Export tasks and summary to Excel (.xlsx) using `openpyxl`

## Setup

```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

