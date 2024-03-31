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
async def read_tasks(db: db_dependency, sort_by: str = "original"):
    order_option = get_order_option(sort_by)
    result = db.query(models.Task).order_by(order_option).all()

    return result


@app.get("/tasks/{task_id}")
async def read_task(task_id: int, db: db_dependency):
    result = db.query(models.Task).get(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    return result


@app.post("/tasks")
async def create_task(task: TaskBase, db: db_dependency):
    date_obj = datetime.strptime(task.date, "%Y-%m-%d").date()

    result = models.Task(title=task.title, description=task.description, date=date_obj,
                         is_completed=task.is_completed, is_important=task.is_important)

    db.add(result)
    db.commit()
    db.refresh(result)

    return result


@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task: TaskBase, db: db_dependency):
    result = db.query(models.Task).get(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    date_obj = datetime.strptime(task.date, "%Y-%m-%d").date()

    result.title = task.title
    result.description = task.description
    result.date = date_obj
    result.is_completed = task.is_completed
    result.is_important = task.is_important

    db.commit()
    db.refresh(result)

    return result


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, db: db_dependency):
    result = db.query(models.Task).get(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(result)
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
