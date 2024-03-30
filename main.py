from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Annotated
from sqlalchemy import desc
from sqlalchemy.orm import Session
from database import engine, SessionLocal
import models

app = FastAPI()

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


@app.get("/tasks")
async def read_tasks(db: db_dependency):
    result = db.query(models.Task).order_by(desc(models.Task.id)).all()
    return result


@app.get("/tasks/{task_id}")
async def read_task(task_id: int, db: db_dependency):
    result = db.query(models.Task).get(task_id)

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    return result


@app.post("/tasks")
async def create_task(task: TaskBase, db: db_dependency):
    result = models.Task(title=task.title, description=task.description, date=task.date,
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

    result.title = task.title
    result.description = task.description
    result.date = task.date
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
