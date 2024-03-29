from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from database import Base


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    date = Column(String)
    is_completed = Column(Boolean, default=False)
    is_important = Column(Boolean, default=False)
