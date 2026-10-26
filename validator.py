from pydantic import BaseModel, EmailStr, Field


class RecordInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=15)


class BulkRecordInput(BaseModel):
    records: list[RecordInput] = Field(min_length=1, max_length=500)
