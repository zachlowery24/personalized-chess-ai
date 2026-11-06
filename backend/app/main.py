from fastapi import FastAPI, HTTPException
import httpx

from backend.app.schemas.game_import import (
    GameImportRequest,
    GameImportResponse,
)
from backend.app.services.game_import import (
    GameProcessingError,
    GameRetrievalError,
    import_recent_games,
)


app = FastAPI(title="Personalized Chess AI")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/imports/chesscom", response_model=GameImportResponse)
def import_chesscom_games(request: GameImportRequest) -> dict:
    try:
        return import_recent_games(request.username, request.count)
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
    


