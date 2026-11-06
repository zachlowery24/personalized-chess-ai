from pydantic import BaseModel, Field, field_validator
from typing import Literal

class GameImportRequest(BaseModel):
    username: str
    count: int = Field(default=5, ge=1, le=100, strict=True)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        username = value.strip().lower()

        if not username:
            raise ValueError("username must not be blank")

        return username


class MoveRecord(BaseModel):
    ply: int = Field(ge=1, strict=True)
    color: Literal["white", "black"]
    uci: str
    san: str
    fen_before: str
    fen_after: str  

class ProcessedGame(BaseModel):
    source: Literal["chess.com"]
    source_url: str
    username: str
    user_color: Literal["white", "black"]
    white_username: str
    black_username: str
    user_result: str
    rules: Literal["chess"]
    time_class: str
    end_time: int = Field(ge=0, strict=True)
    pgn: str
    moves: list[MoveRecord]

class GameImportResponse(BaseModel):
    imported_count: int = Field(ge=0, strict=True)
    processed_count: int = Field(ge=0, strict=True)
    skipped_count: int = Field(ge=0, strict=True)
    games: list[ProcessedGame]