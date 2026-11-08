from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Literal


class GameAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    depth: int = Field(default=12, ge=1, le=20, strict=True)


class GameAnalysisCreatedResponse(BaseModel):
    analysis_id: int = Field(ge=1)
    game_id: int = Field(ge=1)



class SavedMoveAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ply: int
    color: Literal["white", "black"]
    uci: str
    san: str
    fen_before: str
    fen_after: str

    before_best_move: str | None
    before_score_cp: int | None
    before_mate_in: int | None
    before_depth: int | None

    after_best_move: str | None
    after_score_cp: int | None
    after_mate_in: int | None
    after_depth: int | None

    centipawn_loss: int | None


class PlayerAnalysisSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    color: Literal["white", "black"]
    total_moves: int
    scored_moves: int
    unscored_moves: int
    average_centipawn_loss: float | None


class SavedGameAnalysisResponse(BaseModel):
    analysis_id: int
    game_id: int
    engine_name: str
    requested_depth: int
    created_at: datetime
    moves: list[SavedMoveAnalysisResponse]
    white_summary: PlayerAnalysisSummaryResponse
    black_summary: PlayerAnalysisSummaryResponse


class GameAnalysisListItem(BaseModel):
    analysis_id: int
    game_id: int
    engine_name: str
    requested_depth: int
    created_at: datetime

