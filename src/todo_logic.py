from .task_list import tasks, Task, next_id, filter_data
from datetime import datetime, date, timedelta
import calendar

def add_task(title, subject, deadline, description):
    global next_id
    
    task = Task(
        id = next_id,
        title = title,
        subject = subject,
        deadline = deadline,
        description = description,
        creator = "Haris"
    )
    
    tasks.append(task)
    next_id += 1
    
def edit_task(title, subject, deadline, description, task):
    task.title = title
    task.subject = subject
    task.deadline = deadline
    task.description = description
    
def delete_task(task):
    tasks.remove(task)
    
def complete_task(task):
    if task.status:
        task.status = False
        task.done_at = None
    else:
        task.status = True
        task.done_at = datetime.now()
    
def find_task(task_list, key, value, result_key=None):
    for data in task_list:
        if getattr(data, key) == value:
            if result_key == None:
                return data
            return getattr(data, result_key)
    
    return None

def filter_task(tasks, status, subject, deadline,):
    global filter_data
    
    filtered = []
    
    for task in tasks:
        if status == "active" and task.status:
            continue
        
        if status == "completed" and not task.status:
            continue
        
        if subject != "all" and task.subject != subject:
            continue
        
        if not check_deadline(task, deadline):
            continue
        
        filtered.append(task)
    
    filter_data["filter_state"]["status"] = status
    filter_data["filter_state"]["subject"] = subject
    filter_data["filter_state"]["deadline"] = deadline
    
    return filtered
        
def check_deadline(task, deadline):
    task_date = datetime.strptime(task.deadline, "%Y-%m-%d").date()
    today = date.today()
    
    if deadline == "all":
        return True
    
    if deadline == "today":
        return task_date == today
    
    if deadline == "overdue":
        return task_date < today
    
    if deadline == "this_week":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        
        return monday <= task_date <= sunday
    
    if deadline == "next_week":
        monday = today - timedelta(days=today.weekday())
        next_monday = monday + timedelta(days=7)
        next_sunday = next_monday + timedelta(days=6)
        
        return next_monday <= task_date <= next_sunday
    
    if deadline == "this_month":
        first_day = date(today.year, today.month, 1)
        last_day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        
        return first_day <= task_date <= last_day
    
    if deadline == "next_month":
        if today.month == 12:
            next_month = date(today.year + 1, 1, 1)
        else:
            next_month = date(today.year, today.month + 1, 1)
            
        first_day = next_month
        last_day = date(next_month.year, next_month.month , calendar.monthrange(next_month.year, next_month.month)[1])
        
        return first_day <= task_date <= last_day
            