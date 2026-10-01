from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


class DocumentReviewCreate(BaseModel):
    status: Literal["approved", "rejected"]
    rejection_reason: str | None = None

    @field_validator("rejection_reason")
    @classmethod
    def trim_rejection_reason(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.status == "rejected" and not self.rejection_reason:
            raise ValueError("A rejection reason is required")
        return self
