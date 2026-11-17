from typing import Literal

from pydantic import BaseModel, Field


class PracticePositionResponse(BaseModel):
    game_id: int
    analysis_id: int
    ply: int
    color: Literal["white", "black"]
    fen: str
    engine_name: str
    requested_depth: int


class PracticeQueueResponse(BaseModel):
    player_id: int
    positions: list[PracticePositionResponse]
    analyzed_game_count: int = Field(ge=0)


class PracticeRevealResponse(BaseModel):
    game_id: int
    analysis_id: int
    ply: int
    color: Literal["white", "black"]
    fen: str
    played_move: str
    recommended_move: str
    centipawn_loss: int
    engine_name: str
    requested_depth: int


    