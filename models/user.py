import enum
from sqlalchemy import Column, Integer, String, Enum, DateTime, func
from database import Base


class UserRole(str, enum.Enum):
    CLIENT = "client"
    PLANNER = "planner"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
