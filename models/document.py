from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("client_profiles.id"), nullable=False)
    filename = Column(String, nullable=False)
    label = Column(String, nullable=True)  # e.g. "T4 2024", "Group benefits booklet"
    section_key = Column(String, nullable=True)  # links to intake section
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
