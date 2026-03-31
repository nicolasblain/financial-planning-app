from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, func
from database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client_profiles.id"), nullable=False)
    version = Column(Integer, default=1)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # structured JSON plan content
    is_delivered = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlanComment(Base):
    __tablename__ = "plan_comments"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    section_key = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
