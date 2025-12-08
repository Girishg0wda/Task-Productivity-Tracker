from datetime import date, timedelta
import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect

from .forms import TaskForm
from .models import Task

User = get_user_model()


# -------------------------
#   MAIN DASHBOARD (USER)
# -------------------------

@login_required
def task_list(request):
    # Only show tasks of logged-in user
    tasks = Task.objects.filter(user=request.user)

    q = request.GET.get("q")
    status = request.GET.get("status")
    priority = request.GET.get("priority")
    due = request.GET.get("due_date")

    if q:
        tasks = tasks.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if status:
        tasks = tasks.filter(status=status)
    if priority:
        tasks = tasks.filter(priority=priority)
    if due:
        tasks = tasks.filter(due_date=due)

    today = date.today()
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status=Task.STATUS_COMPLETED).count()
    pending_tasks = tasks.filter(status=Task.STATUS_PENDING).count()
    overdue_tasks = (
        tasks.filter(due_date__lt=today)
        .exclude(status=Task.STATUS_COMPLETED)
        .count()
    )
    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks else 0

    # =========================
    #  Daily chart (last 7 days)
    # =========================
    last_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    completed_per_day = []
    for d in last_7_days:
        count = tasks.filter(
            status=Task.STATUS_COMPLETED,
            updated_at__date=d,
        ).count()
        completed_per_day.append(count)
    labels_7_days = [d.strftime("%b %d") for d in last_7_days]

    # =========================
    #  Priority distribution
    # =========================
    priority_counts = tasks.values("priority").annotate(count=Count("id"))
    priority_map = {p["priority"]: p["count"] for p in priority_counts}
    priorities = [choice[0] for choice in Task.PRIORITY_CHOICES]
    priority_labels = [choice[1] for choice in Task.PRIORITY_CHOICES]
    priority_values = [priority_map.get(p, 0) for p in priorities]

    # =========================
    #  Weekly summary (last 4 weeks)
    # =========================
    # Weeks considered Monday–Sunday
    start_of_current_week = today - timedelta(days=today.weekday())
    week_ranges = []
    for i in range(3, -1, -1):  # 3 weeks ago ... this week
        ws = start_of_current_week - timedelta(days=7 * i)
        we = ws + timedelta(days=6)
        week_ranges.append((ws, we))

    week_labels = []
    week_completed_counts = []

    for ws, we in week_ranges:
        count = tasks.filter(
            status=Task.STATUS_COMPLETED,
            updated_at__date__gte=ws,
            updated_at__date__lte=we,
        ).count()
        week_labels.append(f"{ws.strftime('%d %b')} - {we.strftime('%d %b')}")
        week_completed_counts.append(count)

    last_week_count = week_completed_counts[-1] if week_completed_counts else 0
    prev_week_count = week_completed_counts[-2] if len(week_completed_counts) > 1 else 0

    week_change = last_week_count - prev_week_count
    if prev_week_count > 0:
        week_change_percent = round((week_change / prev_week_count) * 100, 1)
    else:
        week_change_percent = None

    context = {
        "tasks": tasks,
        "q": q or "",
        "status": status or "",
        "priority": priority or "",
        "due_date_filter": due or "",
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
        "completion_percentage": round(completion_percentage, 2),
        "chart_labels_7_days": json.dumps(labels_7_days),
        "chart_data_7_days": json.dumps(completed_per_day),
        "priority_labels": json.dumps(priority_labels),
        "priority_values": json.dumps(priority_values),
        "status_choices": Task.STATUS_CHOICES,
        "priority_choices": Task.PRIORITY_CHOICES,
        "today": today,

        # Weekly
        "week_labels": json.dumps(week_labels),
        "week_completed_counts": json.dumps(week_completed_counts),
        "last_week_count": last_week_count,
        "prev_week_count": prev_week_count,
        "week_change": week_change,
        "week_change_percent": week_change_percent,
    }
    return render(request, "tasks/task_list.html", context)


@login_required
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, "Task created successfully.")
            return redirect("tasks:task_list")
    else:
        form = TaskForm()
    return render(request, "tasks/task_form.html", {"form": form, "is_create": True})


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully.")
            return redirect("tasks:task_list")
    else:
        form = TaskForm(instance=task)
    return render(
        request,
        "tasks/task_form.html",
        {"form": form, "task": task, "is_create": False},
    )


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, user=request.user)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect("tasks:task_list")
    return render(request, "tasks/task_confirm_delete.html", {"task": task})


@login_required
def task_change_status(request, pk, status):
    valid_statuses = [s[0] for s in Task.STATUS_CHOICES]
    if status not in valid_statuses:
        return HttpResponseBadRequest("Invalid status")

    try:
        task = Task.objects.get(pk=pk, user=request.user)
    except Task.DoesNotExist:
        messages.error(request, "Task not found or does not belong to you.")
        return redirect("tasks:task_list")

    task.status = status
    task.save()
    messages.success(request, "Status updated.")
    return redirect("tasks:task_list")


@login_required
def export_tasks_excel(request):
    try:
        from openpyxl import Workbook
    except ImportError:
        return HttpResponse("openpyxl not installed", content_type="text/plain")

    wb = Workbook()
    ws = wb.active
    ws.title = "Tasks"
    ws.append(["ID", "Title", "Priority", "Due Date", "Status", "Created"])

    for task in Task.objects.filter(user=request.user).order_by("id"):
        ws.append(
            [
                task.id,
                task.title,
                task.get_priority_display(),
                task.due_date.isoformat() if task.due_date else "",
                task.get_status_display(),
                task.created_at.strftime("%Y-%m-%d"),
            ]
        )

    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    )
    response["Content-Disposition"] = "attachment; filename=tasks.xlsx"
    wb.save(response)
    return response


# -------------------------
#   AUTH: SIGNUP
# -------------------------

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("tasks:task_list")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


# -------------------------
#   TEAM OVERVIEW (HR / TL)
# -------------------------

def is_team_lead(user):
    # Treat staff / superuser as HR / Team Lead
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_team_lead)
def team_overview(request):
    today = date.today()

    # Aggregate counts per user
    users = (
        User.objects.annotate(
            total_tasks=Count("tasks", distinct=True),
            completed_tasks=Count(
                "tasks",
                filter=Q(tasks__status=Task.STATUS_COMPLETED),
                distinct=True,
            ),
            pending_tasks=Count(
                "tasks",
                filter=Q(tasks__status=Task.STATUS_PENDING),
                distinct=True,
            ),
            in_progress_tasks=Count(
                "tasks",
                filter=Q(tasks__status=Task.STATUS_IN_PROGRESS),
                distinct=True,
            ),
            # Overdue = due_date < today AND status is either pending or in_progress
            overdue_tasks=Count(
                "tasks",
                filter=Q(
                    tasks__due_date__lt=today,
                    tasks__status__in=[Task.STATUS_PENDING, Task.STATUS_IN_PROGRESS],
                ),
                distinct=True,
            ),
        )
        .order_by("username")
    )

    # Optional: show only users who have at least one task
    users = [u for u in users if u.total_tasks > 0]

    return render(
        request,
        "tasks/team_overview.html",
        {"users": users, "today": today},
    )
