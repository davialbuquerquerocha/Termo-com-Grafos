"""Entropy-based Termo solver.

Use ``strategy="entropy"`` for ordinary entropy ranking, or
``strategy="groups"`` to recursively evaluate the feedback groups produced by
each guess. ``"deep"`` remains available as an alias for ``"groups"``.
"""

from .algorithm import (
    SolverEvaluation,
    Strategy,
    AnswerList,
    best_move,
    choose_first_guess,
    choose_guess,
    evaluate_guess,
    evaluate_solver,
    interactive_play,
    main,
    simulate_game,
)
from . import functions
from .functions import (
    SearchProfile,
    entropy,
    memo_store_stats,
    parse_feedback,
    partitioning,
    profile_search,
    ranking,
)

__all__ = [
    "SolverEvaluation",
    "SearchProfile",
    "Strategy",
    "AnswerList",
    "best_move",
    "choose_first_guess",
    "choose_guess",
    "entropy",
    "evaluate_guess",
    "evaluate_solver",
    "functions",
    "interactive_play",
    "memo_store_stats",
    "main",
    "parse_feedback",
    "partitioning",
    "profile_search",
    "ranking",
    "simulate_game",
]
