from flask import Flask, render_template, request, redirect, url_for
from src import task_list
from src import todo_logic

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", tasks=task_list.tasks)

@app.route("/task", methods=["GET"])
def task():
    status = request.args.get("status", "all")
    subject = request.args.get("subject", "all")
    deadline = request.args.get("deadline", "all")
            
    task_filtered = todo_logic.filter_task(
        tasks=task_list.tasks,
        status=status,
        subject=subject,
        deadline=deadline
        )
        
    return render_template("tasks/task.html",
                            tasks=task_filtered,
                            filter_data=task_list.filter_data
                           )

@app.route("/task/add", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        title = request.form["title"]
        subject = request.form["subject"]
        deadline = request.form["deadline"]
        description = request.form["description"]
        
        todo_logic.add_task(
            title=title,
            subject=subject,
            deadline=deadline,
            description=description
        )
        
        return redirect(url_for("task"))
    
    return render_template("tasks/add.html")

@app.route("/task/edit/id=<int:id>", methods=["GET", "POST"])
def edit_task(id):
    task = todo_logic.find_data(task_list.tasks, "id", id,)
    
    if request.method == "POST":
        title = request.form["title"]
        subject = request.form["subject"]
        deadline = request.form["deadline"]
        description = request.form["description"]
        
        todo_logic.edit_task(title, subject, deadline, description, task)
        
        return redirect(url_for("task"))
    
    return render_template("/tasks/edit.html",
                           task = task,
                           subjects = task_list.subjects
                           )
    
@app.route("/task/delete/id=<int:id>", methods=["POST"])
def delete_task(id):
    task = todo_logic.find_data(task_list.tasks, "id", id,)
    
    todo_logic.delete_task(task)
    
    return redirect(url_for("task"))

@app.route("/task/complete/id=<int:id>", methods=["POST"])
def complete_task(id):
    task = todo_logic.find_data(task_list.tasks, "id", id,)
    
    todo_logic.complete_task(task)
    
    return redirect(url_for("task"))

if __name__ == "__main__":
    app.run(debug=True,port=5000)