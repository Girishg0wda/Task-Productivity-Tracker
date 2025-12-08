from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('task/add/', views.task_create, name='task_create'),
    path('task/<int:pk>/edit/', views.task_update, name='task_update'),
    path('task/<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('task/<int:pk>/status/<str:status>/', views.task_change_status, name='task_change_status'),
    path('export/excel/', views.export_tasks_excel, name='export_tasks_excel'),
    path('signup/', views.signup, name='signup'),
     path('team/overview/', views.team_overview, name='team_overview'),
]
