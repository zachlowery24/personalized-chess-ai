from backend.app.services.pgn import (
    extract_move_positions,
    parse_pgn_games,
)


class GameReplayError(Exception):
    """A saved game's PGN could not produce valid replay data."""


def build_game_moves(pgn_text: str) -> list[dict]:
    try:
        games = parse_pgn_games(pgn_text)

        if len(games) != 1:
            raise GameReplayError(
                "Saved PGN must contain exactly one playable game."
            )

        game = games[0]

        if game.board().uci_variant != "chess":
            raise GameReplayError(
                "Only standard chess is supported."
            )

        return extract_move_positions(game)

    except ValueError as error:
        raise GameReplayError(
            "Saved PGN could not be processed."
        ) from error