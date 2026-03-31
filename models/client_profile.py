import enum
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class CycleStage(str, enum.Enum):
    INTAKE = "intake"
    GOALS = "goals"
    ANALYSIS = "analysis"
    PLAN_DRAFTING = "plan_drafting"
    PLAN_DELIVERY = "plan_delivery"
    MONITORING = "monitoring"


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    planner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    cycle_stage = Column(Enum(CycleStage), default=CycleStage.INTAKE)
    employment_type = Column(String, nullable=True)  # employed, self_employed
    household_type = Column(String, nullable=True)    # individual, couple
    housing_status = Column(String, nullable=True)    # owner, renter
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    planner = relationship("User", foreign_keys=[planner_id])
