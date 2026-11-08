from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlayerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    username: str
    created_at: datetime