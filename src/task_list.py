
# Bentukan Full Tasks
# tasks = [
#     {
#         "id" : 1
#         "title" : "Judul",
#         "subject" : "tugas",
#         "deadline": "Tanggal",
#         "status": False,
#         "description": "Tugas tetang ini",
#         "done_at": "Tanggal Selesai",
#         "create_at": "Tanggal Di Buat",
#         "creator": "user pembuat"        
#     }
# ]

from dataclasses import dataclass, field
from datetime import datetime

next_id = 4

@dataclass
class Task:
    id: int
    title: str
    subject: str
    deadline: str
    status: bool = False
    description: str = ""
    done_at: str | None = None
    create_at: datetime = field(default_factory=datetime.now)
    creator: str = ""
    
subjects = ["tugas", "project", "random"]

filter_data = {
    "filter_list" : {
        "status" : [
            "all",
            "active",
            "completed"
        ],
        "subject" : [
            "all",
            "tugas",
            "project",
            "random"
        ],
        "deadline" : [
            "all",
            "overdue",
            "today",
            "tomorrow",
            "this_week",
            "next_week",
            "this_month",
            "next_month"
        ]
    },
    "filter_state" : {
        "status" : "all",
        "subject" : "all",
        "deadline" : "all"
    }
}

tasks = [
    Task(
        id=1,
        title="PR MTK",
        subject="tugas",
        deadline="2026-10-05",
        status=True,
        description="Tugas MTK Limit",
        done_at=None,
        creator="Haris"
    ),

    Task(
        id=2,
        title="Belajar Flask",
        subject="project",
        deadline="2026-10-03",
        status=False,
        description="Project buat WEB pake Flask",
        done_at=None,
        creator="Haris"
    ),

    Task(
        id=3,
        title="buat Todo Web",
        subject="project",
        deadline="2026-10-10",
        status=False,
        description="Project buat Todo",
        done_at=None,
        creator="Haris"
    )
]