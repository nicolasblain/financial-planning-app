from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, func
from database import Base


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client_profiles.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=0)  # higher = more important
    time_horizon = Column(String, nullable=True)  # "5_years", "10_years", "20_years"
    category = Column(String, nullable=True)  # "retirement", "home", "education", "protection"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
