from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, func
from database import Base


class IntakeSection(Base):
    """Defines the sections of the adaptive intake questionnaire."""
    __tablename__ = "intake_sections"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)  # e.g. "income", "assets", "liabilities"
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order = Column(Integer, nullable=False)
    condition = Column(String, nullable=True)  # JSON condition for adaptive display


class IntakeResponse(Base):
    """Stores a client's responses to intake questions."""
    __tablename__ = "intake_responses"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client_profiles.id"), nullable=False)
    section_key = Column(String, ForeignKey("intake_sections.key"), nullable=False)
    data = Column(Text, nullable=False)  # JSON blob of field responses
    is_complete = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
