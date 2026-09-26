from sqlalchemy import Column, Integer, String
from database import Base


class Record(Base):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    email = Column(String, nullable=False)

    phone = Column(String, nullable=False)

    record_hash = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )