from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.schemas.game_import import MoveRecord


class SavedGameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_url: str
    white_player_id: int
    black_player_id: int
    white_result: str
    black_result: str
    time_class: str
    rules: Literal["chess"]
    ended_at: datetime
    pgn: str
    created_at: datetime

class GameMovesResponse(BaseModel):
    game_id: int
    moves: list[MoveRecord]