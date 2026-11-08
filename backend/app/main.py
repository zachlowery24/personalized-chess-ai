from typing import Annotated, Literal
import chess.engine

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.app.repositories.games import (
    get_game_by_id,
    list_games_for_player,
)

from backend.app.schemas.game import SavedGameResponse, GameMovesResponse

from backend.app.database import get_session_factory
from backend.app.schemas.game_import import (
    GameImportRequest,
    GameImportResponse,
)
from backend.app.services.game_import import (
    GameProcessingError,
    GameRetrievalError,
    GameStorageError,
    import_recent_games,
)
from backend.app.repositories.players import get_player_by_username
from backend.app.schemas.player import PlayerProfileResponse

from backend.app.services.game_replay import (
    GameReplayError,
    build_game_moves,
)

from backend.app.config import Settings

from backend.app.schemas.game_analysis import (
    GameAnalysisCreatedResponse,
    GameAnalysisRequest,
    SavedGameAnalysisResponse,
    SavedMoveAnalysisResponse,
    GameAnalysisListItem,
    PlayerAnalysisSummaryResponse
)

from backend.app.services.game_analysis import (
    GameNotFoundError,
    analyze_saved_game,
)

from backend.app.repositories.analyses import (
    get_game_analysis_by_id,
    list_analysis_moves,
    list_game_analyses
)

from backend.app.services.engine_analysis import summarize_player_analysis




app = FastAPI(title="Personalized Chess AI")


def get_settings() -> Settings:
    return Settings()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/imports/chesscom", response_model=GameImportResponse)
def import_chesscom_games(
    request: GameImportRequest,
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
) -> dict:
    try:
        return import_recent_games(
            request.username,
            request.count,
            session_factory=session_factory,
        )
    except GameRetrievalError:
        raise HTTPException(
            status_code=502,
            detail="Chess.com returned invalid game data.",
        ) from None
    except GameProcessingError:
        raise HTTPException(
            status_code=502,
            detail="The games returned by Chess.com could not be processed.",
        ) from None
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Chess.com did not respond in time.",
        ) from None
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Could not complete the request to Chess.com.",
        ) from None
    except httpx.HTTPStatusError as error:
        upstream_status = error.response.status_code

        if upstream_status == 404:
            raise HTTPException(
                status_code=404,
                detail="The requested Chess.com resource was not found.",
            ) from None

        if upstream_status == 429:
            raise HTTPException(
                status_code=503,
                detail="Chess.com is temporarily rate-limiting requests. Try again later.",
            ) from None

        raise HTTPException(
            status_code=502,
            detail="Chess.com returned an unsuccessful response.",
        ) from None

    except GameStorageError:
        raise HTTPException(
            status_code=503,
            detail="Imported games could not be saved. Please try again later.",
        ) from None
    
@app.get("/games/{game_id}", response_model=SavedGameResponse)
def get_saved_game(
    game_id: Annotated[int, Path(ge=1)],
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
) -> SavedGameResponse:
    try:
        with session_factory() as session:
            game = get_game_by_id(session, game_id)

            if game is None:
                raise HTTPException(
                    status_code=404,
                    detail="Game not found.",
                )

            return SavedGameResponse.model_validate(game)

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Saved games are temporarily unavailable.",
        ) from None

@app.get(
    "/players/{player_id}/games",
    response_model=list[SavedGameResponse],
)
def get_player_games(
    player_id: Annotated[int, Path(ge=1)],
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    time_class: Annotated[
        Literal["bullet", "blitz", "rapid", "daily"] | None,
        Query(),
    ] = None,
) -> list[SavedGameResponse]:
    try:
        with session_factory() as session:
            games = list_games_for_player(
                session,
                player_id,
                limit=limit,
                offset=offset,
                time_class=time_class,
            )

            return [
                SavedGameResponse.model_validate(game)
                for game in games
            ]

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Saved games are temporarily unavailable.",
        ) from None


@app.get("/players/lookup", response_model=PlayerProfileResponse)
def lookup_player(
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
    username: Annotated[
        str,
        Query(min_length=1, max_length=255, pattern=r"\S"),
    ],
    source: Annotated[
        Literal["chess.com"],
        Query(),
    ] = "chess.com",
) -> PlayerProfileResponse:
    try:
        with session_factory() as session:
            player = get_player_by_username(
                session,
                source,
                username,
            )

            if player is None:
                raise HTTPException(
                    status_code=404,
                    detail="Player not found.",
                )

            return PlayerProfileResponse.model_validate(player)

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Player profiles are temporarily unavailable.",
        ) from None


@app.get("/games/{game_id}/moves", response_model=GameMovesResponse)
def get_saved_game_moves(
    game_id: Annotated[int, Path(ge=1)],
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
) -> GameMovesResponse:
    try:
        with session_factory() as session:
            game = get_game_by_id(session, game_id)

            if game is None:
                raise HTTPException(
                    status_code=404,
                    detail="Game not found.",
                )

            pgn_text = game.pgn

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Saved games are temporarily unavailable.",
        ) from None

    try:
        moves = build_game_moves(pgn_text)

    except GameReplayError:
        raise HTTPException(
            status_code=500,
            detail="The saved game could not be replayed.",
        ) from None

    return GameMovesResponse(
        game_id=game_id,
        moves=moves,
    )



@app.post(
    "/games/{game_id}/analyses",
    response_model=GameAnalysisCreatedResponse,
    status_code=201,
)
def create_saved_game_analysis(
    game_id: Annotated[int, Path(ge=1)],
    request: GameAnalysisRequest,
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GameAnalysisCreatedResponse:
    try:
        analysis_id = analyze_saved_game(
            game_id,
            session_factory=session_factory,
            engine_path=settings.stockfish_path,
            depth=request.depth,
        )

    except GameNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Game not found.",
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Game analysis storage is temporarily unavailable.",
        ) from None

    except (chess.engine.EngineError, OSError, TimeoutError):
        raise HTTPException(
            status_code=503,
            detail="The chess engine is temporarily unavailable.",
        ) from None

    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="The saved game could not be analyzed.",
        ) from None

    return GameAnalysisCreatedResponse(
        analysis_id=analysis_id,
        game_id=game_id,
    )

@app.get(
    "/analyses/{analysis_id}",
    response_model=SavedGameAnalysisResponse,
)
def get_saved_analysis(
    analysis_id: Annotated[int, Path(ge=1)],
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
) -> SavedGameAnalysisResponse:
    try:
        with session_factory() as session:
            analysis = get_game_analysis_by_id(session, analysis_id)

            if analysis is None:
                raise HTTPException(
                    status_code=404,
                    detail="Analysis not found.",
                )

            moves = list_analysis_moves(session, analysis_id)

            return SavedGameAnalysisResponse(
                analysis_id=analysis.id,
                game_id=analysis.game_id,
                engine_name=analysis.engine_name,
                requested_depth=analysis.requested_depth,
                created_at=analysis.created_at,
                moves=[
                    SavedMoveAnalysisResponse.model_validate(move)
                    for move in moves
                ],
                 white_summary=PlayerAnalysisSummaryResponse.model_validate(
                    summarize_player_analysis(moves, color="white")
                ),
                black_summary=PlayerAnalysisSummaryResponse.model_validate(
                    summarize_player_analysis(moves, color="black")
                ),
            )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Saved analyses are temporarily unavailable.",
        ) from None


@app.get(
    "/games/{game_id}/analyses",
    response_model=list[GameAnalysisListItem],
)
def get_game_analyses(
    game_id: Annotated[int, Path(ge=1)],
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[GameAnalysisListItem]:
    try:
        with session_factory() as session:
            game = get_game_by_id(session, game_id)

            if game is None:
                raise HTTPException(
                    status_code=404,
                    detail="Game not found.",
                )

            analyses = list_game_analyses(
                session,
                game_id,
                limit=limit,
                offset=offset,
            )

            return [
                GameAnalysisListItem(
                    analysis_id=analysis.id,
                    game_id=analysis.game_id,
                    engine_name=analysis.engine_name,
                    requested_depth=analysis.requested_depth,
                    created_at=analysis.created_at,
                )
                for analysis in analyses
            ]

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Saved analyses are temporarily unavailable.",
        ) from None
