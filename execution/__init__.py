"""
Package execution per elaborazione, parsing e persistenza quotazioni futures cereali.
"""

from .storage_manager import (
    load_quotes,
    add_quotes,
    save_quotes,
    get_quotes_for_selection,
    get_delta_for_selection,
    sync_from_github,
    sync_to_github,
    get_latest_db_date
)

__all__ = [
    "load_quotes",
    "add_quotes",
    "save_quotes",
    "get_quotes_for_selection",
    "get_delta_for_selection",
    "sync_from_github",
    "sync_to_github",
    "get_latest_db_date"
]
