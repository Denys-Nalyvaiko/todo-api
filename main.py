from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Annotated
from sqlalchemy import desc
from sqlalchemy.orm import Session
from datetime import datetime
from database import engine, SessionLocal
import models
import auth

app = FastAPI()
app.include_router(auth.router)

# TODO remove temporary * from origins
origins = [
    "http://localhost:3000",
    "https://todo-app-rho-sand.vercel.app/",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

models.Base.metadata.create_all(bind=engine)


class TaskBase(BaseModel):
    title: str
    description: str
    date: str
    is_completed: bool
    is_important: bool


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(auth.get_current_user)]


@app.get("/users/current")
async def get_current_user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed")

    return user


@app.get("/tasks")
async def read_tasks(db: db_dependency, user: user_dependency, sort_by: str = "original"):
    order_option = get_order_option(sort_by)
    tasks = (db.query(models.Task)
             .filter(models.Task.user_id == user['user']['id'])
             .order_by(order_option).all())

    return tasks


@app.get("/tasks/{task_id}")
async def read_task(task_id: int, db: db_dependency, user: user_dependency):
    task = (db.query(models.Task)
            .filter(models.Task.id == task_id, models.Task.user_id == user['user']['id'])
            .first())

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@app.post("/tasks")
async def create_task(task: TaskBase, db: db_dependency, user: user_dependency):
    date_obj = datetime.strptime(task.date, "%Y-%m-%d").date()

    new_task = models.Task(title=task.title, description=task.description, date=date_obj,
                           is_completed=task.is_completed, is_important=task.is_important,
                           user_id=user['user']['id'])

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task


@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task: TaskBase, db: db_dependency, user: user_dependency):
    target_task = (db.query(models.Task)
                   .filter(models.Task.id == task_id, models.Task.user_id == user['user']['id'])
                   .first())

    if not target_task:
        raise HTTPException(status_code=404, detail="Task not found")

    date_obj = datetime.strptime(task.date, "%Y-%m-%d").date()

    target_task.title = task.title
    target_task.description = task.description
    target_task.date = date_obj
    target_task.is_completed = task.is_completed
    target_task.is_important = task.is_important

    db.commit()
    db.refresh(target_task)

    return target_task


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, db: db_dependency, user: user_dependency):
    task = (db.query(models.Task)
            .filter(models.Task.id == task_id, models.Task.user_id == user['user']['id'])
            .first())

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

    return {"message": "Task deleted successfully"}


def get_order_option(sort_by: str):
    order_options = {
        "original": desc(models.Task.id),
        "title_asc": models.Task.title,
        "title_desc": desc(models.Task.title),
        "date_asc": models.Task.date,
        "date_desc": desc(models.Task.date)
    }

    return order_options.get(sort_by, desc(models.Task.id))
