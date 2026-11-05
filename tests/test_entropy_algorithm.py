from collections.abc import Iterable
from concurrent.futures import Future, wait as futures_wait
from pathlib import Path
from contextlib import redirect_stdout
import hashlib
import io
import json
import random
import re
import sqlite3
import tempfile
from threading import Event, Thread
import time
from typing import Any
import unittest
from unittest.mock import patch

import numpy as np

import algorithm.entropy as entropy_package
from algorithm.entropy import algorithm as solver
from algorithm.entropy import functions as helpers
from algorithm.partition import functions as partition_functions


class EntropyAlgorithmTests(unittest.TestCase):
    def test_evaluation_scope_key_supports_accented_answers(self) -> None:
        expected = hashlib.sha256("ÁUDIO\0".encode("utf-8")).hexdigest()

        self.assertEqual(helpers.evaluation_scope_key(["ÁUDIO"]), expected)

    def test_load_answers_selects_between_accepted_and_solution_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            accepted_path = Path(directory) / "termo_palavras_aceitas.txt"
            accepted_path.write_text("AAAAA\nBBBBB\n", encoding="utf-8")
            accepted_path.with_name(
                "termo_solucoes_possiveis.txt"
            ).write_text("BBBBB\n", encoding="utf-8")

            with patch.object(
                partition_functions,
                "DATASET_PATH",
                accepted_path,
            ):
                self.assertEqual(
                    solver._load_answers("accepted"),
                    ["AAAAA", "BBBBB"],
                )
                self.assertEqual(
                    solver._load_answers("solutions"),
                    ["BBBBB"],
                )

    def test_first_guess_cache_uses_guess_vocabulary_indices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            accepted_path = Path(directory) / "termo_palavras_aceitas.txt"
            accepted_path.write_text(
                "AAAAA\nBBBBB\nCCCCC\n",
                encoding="utf-8",
            )
            accepted_path.with_name(
                "termo_solucoes_possiveis.txt"
            ).write_text("CCCCC\nAAAAA\n", encoding="utf-8")

            with (
                patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    accepted_path,
                ),
                patch.object(solver, "best_move", return_value=(1, 1.5)),
            ):
                first_result = solver.choose_first_guess(answer_list="solutions")
                cache_path = accepted_path.with_name(
                    "entropy_first_guess_solutions.json"
                )
                cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
                cached_result = solver.choose_first_guess(
                    answer_list="solutions"
                )

            self.assertEqual(first_result, (1, 1.5))
            self.assertEqual(cached_result, first_result)
            self.assertEqual(cache_data["guess"], "BBBBB")

    def test_play_cli_forwards_selected_answer_list(self) -> None:
        with patch.object(solver, "interactive_play") as interactive_play:
            solver.main(["play", "--answer-list", "solutions"])

        interactive_play.assert_called_once_with("entropy", "solutions")

    def test_evaluate_cli_samples_and_forwards_selected_answer_list(self) -> None:
        result = solver.SolverEvaluation(
            1.0,
            1,
            ("AAAAA",),
            {1: 1},
            1.0,
            1,
        )
        with (
            patch.object(solver, "_load_answers", return_value=["AAAAA"]) as load_answers,
            patch.object(solver, "evaluate_solver", return_value=result) as evaluate,
            redirect_stdout(io.StringIO()),
        ):
            solver.main(
                [
                    "evaluate",
                    "--answer-list",
                    "solutions",
                    "--sample-size",
                    "1",
                ]
            )

        load_answers.assert_called_once_with("solutions")
        evaluate.assert_called_once_with(
            "entropy",
            answers=["AAAAA"],
            resume=True,
            checkpoint_interval=100,
            workers=1,
            answer_list="solutions",
        )

    def test_entropy_package_exports_both_strategies(self) -> None:
        self.assertIs(entropy_package.interactive_play, solver.interactive_play)
        self.assertIs(entropy_package.entropy, helpers.entropy)
        self.assertEqual(solver._validate_strategy("entropy"), "entropy")
        self.assertEqual(solver._validate_strategy("groups"), "deep")
        self.assertEqual(solver._validate_strategy("deep"), "deep")

        with self.assertRaises(ValueError):
            solver._validate_strategy("unknown")

    def test_entropy_chooses_first_candidate_when_two_remain(self) -> None:
        words = ["AAAAA", "BBBBB"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.zeros((2, 2), dtype=np.uint8),
            "test",
        )

        with tempfile.TemporaryDirectory() as directory:
            word_list_path = Path(directory) / "words.txt"
            word_list_path.write_text("\n".join(words), encoding="utf-8")
            with (
                patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    word_list_path,
                ),
                patch.object(
                    helpers,
                    "ranking_with_context",
                    side_effect=AssertionError("two-candidate shortcut should run"),
                ),
            ):
                guess_index = solver._choose_guess_with_context(
                    words,
                    "entropy",
                    0,
                    context,
                )

        self.assertEqual(guess_index, 0)

    def test_rank_state_applies_k_to_all_guesses_but_keeps_exhaustive_oov(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC", "DDDDD", "EEEEE"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray(
                [
                    [242, 0, 0, 0, 0],
                    [0, 242, 0, 0, 0],
                    [0, 0, 242, 0, 0],
                    [0, 0, 0, 242, 0],
                    [0, 0, 0, 0, 242],
                ],
                dtype=np.uint8,
            ),
            "test",
        )
        original_settings = (
            helpers.EXHAUSTIVE_LIMIT,
            helpers.BUDGET,
            helpers.FACTOR,
            helpers.MIN_K,
            helpers.ENTROPY_MARGIN,
            helpers.MAX_K,
        )

        with tempfile.TemporaryDirectory() as directory:
            word_list_path = Path(directory) / "words.txt"
            word_list_path.write_text("\n".join(words[:4]), encoding="utf-8")
            try:
                with patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    word_list_path,
                ):
                    helpers._guess_count.cache_clear()
                    helpers.EXHAUSTIVE_LIMIT = 1
                    helpers.BUDGET = 1
                    helpers.FACTOR = 4
                    helpers.MIN_K = 2
                    helpers.ENTROPY_MARGIN = 100.0
                    bounded = helpers._rank_state(words[:4], 0, context)
                    self.assertEqual(len(bounded), 2)
                    candidate_indices = np.arange(4)
                    entropies = np.asarray(
                        [
                            -sum(
                                (count / 4) * np.log2(count / 4)
                                for count in np.bincount(
                                    context[2][guess_index, candidate_indices],
                                    minlength=243,
                                )
                                if count
                            )
                            for guess_index in range(len(words))
                        ]
                    )
                    expected_bounded = np.argsort(
                        -entropies,
                        kind="stable",
                    )[:2].tolist()
                    self.assertEqual(bounded, expected_bounded)

                    helpers.EXHAUSTIVE_LIMIT = 4
                    exhaustive = helpers._rank_state(
                        [*words[:3], words[4]],
                        0,
                        context,
                    )
                    self.assertEqual(set(exhaustive), set(range(len(words))))
                    helpers.MAX_K = 2
                    capped_exhaustive = helpers._rank_state(
                        [*words[:3], words[4]],
                        0,
                        context,
                    )
                    self.assertEqual(len(capped_exhaustive), 2)
            finally:
                helpers._guess_count.cache_clear()
                (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
                    helpers.MAX_K,
                ) = original_settings

    def test_max_k_caps_guess_count_for_exhaustive_states(self) -> None:
        with (
            patch.object(helpers, "MAX_K", 2),
            patch.object(helpers, "EXHAUSTIVE_LIMIT", 30),
            patch.object(helpers, "_guess_count", return_value=100),
        ):
            self.assertEqual(helpers.k_by_size(5), 2)

    def test_search_settings_report_effective_min_k_and_accept_legacy(self) -> None:
        with (
            patch.object(helpers, "MIN_K", 5),
            patch.object(helpers, "MAX_K", 1),
        ):
            settings = solver._search_settings()
            self.assertEqual(settings["min_k"], 1)
            self.assertEqual(settings["configured_min_k"], 5)
            self.assertEqual(settings["max_k"], 1)

            legacy_settings = settings.copy()
            legacy_settings["min_k"] = legacy_settings.pop("configured_min_k")
            self.assertTrue(solver._search_settings_match(legacy_settings))

    def test_stable_top_k_matches_full_stable_sort(self) -> None:
        rng = np.random.default_rng(2026)
        values = rng.integers(0, 8, size=1_000).astype(np.float64)

        for limit in (0, 1, 3, 25, len(values), len(values) + 1):
            with self.subTest(limit=limit):
                expected = np.argsort(-values, kind="stable")[:limit]
                actual = helpers._stable_top_k_indices(values, limit)
                np.testing.assert_array_equal(actual, expected)

    def test_groups_cli_sets_max_k(self) -> None:
        with (
            patch.object(helpers, "MAX_K", None),
            patch.object(solver, "interactive_play") as interactive_play,
        ):
            solver.main(
                ["play", "--strategy", "groups", "--max-k", "7"]
            )

            self.assertEqual(helpers.MAX_K, 7)
            interactive_play.assert_called_once_with("groups", "accepted")

    def test_best_move_forwards_search_depth(self) -> None:
        words = ["AAAAA", "BBBBB"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.zeros((2, 2), dtype=np.uint8),
            "test",
        )
        with (
            patch.object(solver, "_search_context", return_value=context),
            patch.object(helpers, "_best_move", return_value=(1, 1.5)) as best_move,
        ):
            result = solver.best_move(words, depth=3)

        self.assertEqual(result, (1, 1.5))
        best_move.assert_called_once_with(words, 3, context)

    def test_best_move_rejects_states_after_six_attempts(self) -> None:
        words = ["AAAAA"]
        context = (
            words,
            {"AAAAA": 0},
            np.asarray([[242]], dtype=np.uint8),
            "test",
        )

        result = helpers._best_move(words, helpers.MAX_ATTEMPTS, context)

        self.assertEqual(result[0], -1)
        self.assertTrue(np.isinf(result[1]))

    def test_best_move_rejects_a_state_with_no_feasible_guess(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray(
                [[242, 0, 0], [0, 242, 0], [0, 0, 242]],
                dtype=np.uint8,
            ),
            "test",
        )
        with tempfile.TemporaryDirectory() as directory:
            memo_path = Path(directory) / "memo.sqlite3"
            helpers.configure_memo_store(memo_path, "test")
            try:
                with (
                    patch.object(helpers, "_rank_state", return_value=[0]),
                    patch.object(
                        helpers,
                        "_evaluate_guess",
                        return_value=float("inf"),
                    ),
                ):
                    result = helpers._best_move(
                        words,
                        helpers.MAX_ATTEMPTS - 1,
                        context,
                    )

                self.assertEqual(result[0], -1)
                self.assertTrue(np.isinf(result[1]))
            finally:
                helpers.close_memo_store()

    def test_best_move_persists_infeasible_states_in_memo(self) -> None:
        words = ["AAAAA", "BBBBB"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray([[242, 0], [0, 242]], dtype=np.uint8),
            "test",
        )
        with tempfile.TemporaryDirectory() as directory:
            memo_path = Path(directory) / "memo.sqlite3"
            helpers.configure_memo_store(memo_path, "test")
            try:
                first_result = helpers._best_move(
                    words,
                    helpers.MAX_ATTEMPTS - 1,
                    context,
                )
                helpers.close_memo_store()
                helpers.configure_memo_store(memo_path, "test")
                with helpers.profile_search() as profile:
                    second_result = helpers._best_move(
                        words,
                        helpers.MAX_ATTEMPTS - 1,
                        context,
                    )

                self.assertEqual(first_result[0], -1)
                self.assertTrue(np.isinf(first_result[1]))
                self.assertEqual(second_result, first_result)
                self.assertEqual(profile.states_computed, 0)
                self.assertEqual(profile.memo_hits, 1)
                self.assertEqual(helpers.memo_store_stats()["database_rows"], 1)
            finally:
                helpers.close_memo_store()

    def test_evaluate_guess_stops_after_an_infeasible_feedback_group(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray(
                [[242, 0, 1], [0, 242, 2], [1, 2, 242]],
                dtype=np.uint8,
            ),
            "test",
        )
        with patch.object(
            helpers,
            "_best_move",
            return_value=(-1, float("inf")),
        ) as best_move:
            cost = helpers._evaluate_guess(
                0,
                words,
                float("inf"),
                0,
                context,
            )

        self.assertTrue(np.isinf(cost))
        self.assertEqual(best_move.call_count, 1)

    def test_best_move_raises_when_no_six_guess_strategy_exists(self) -> None:
        words = ["AAAAA", "BBBBB"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.zeros((2, 2), dtype=np.uint8),
            "test",
        )
        with (
            patch.object(solver, "_search_context", return_value=context),
            patch.object(
                helpers,
                "_best_move",
                return_value=(-1, float("inf")),
            ),
            self.assertRaisesRegex(RuntimeError, "within 6 guesses"),
        ):
            solver.best_move(words)

    def test_simulation_increments_search_depth_after_each_guess(self) -> None:
        words = ["AAAAA", "BBBBB"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray([[242, 0], [0, 242]], dtype=np.uint8),
            "test",
        )
        with (
            patch.object(solver, "_load_answers", return_value=words) as load_answers,
            patch.object(solver, "_search_context", return_value=context),
            patch.object(
                solver,
                "choose_first_guess",
                return_value=(0, 1.5),
            ) as first_guess,
            patch.object(solver, "_choose_guess_with_context", return_value=1) as choose_guess,
        ):
            attempts = solver.simulate_game("BBBBB", "deep", "solutions")

        self.assertEqual(attempts, 2)
        load_answers.assert_called_once_with("solutions")
        first_guess.assert_called_once_with(answer_list="solutions")
        choose_guess.assert_called_once_with(["BBBBB"], "deep", 1, context)

    def test_memo_key_changes_when_search_settings_change(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC"]
        matrix = np.asarray(
            [
                [242, 0, 0],
                [0, 242, 0],
                [0, 0, 242],
            ],
            dtype=np.uint8,
        )
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            matrix,
            "test",
        )
        original_settings = (
            helpers.EXHAUSTIVE_LIMIT,
            helpers.BUDGET,
            helpers.FACTOR,
            helpers.MIN_K,
            helpers.ENTROPY_MARGIN,
            helpers.MAX_K,
        )

        with tempfile.TemporaryDirectory() as directory:
            word_list_path = Path(directory) / "words.txt"
            word_list_path.write_text("\n".join(words), encoding="utf-8")
            try:
                with patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    word_list_path,
                ):
                    helpers._guess_count.cache_clear()
                    helpers._BEST_MOVE_CACHE.clear()
                    helpers.EXHAUSTIVE_LIMIT = 3
                    helpers.BUDGET = 100
                    helpers.FACTOR = 4
                    helpers.MIN_K = 1
                    helpers.ENTROPY_MARGIN = 100.0
                    helpers.configure_memo_store(
                        Path(directory) / "memo.sqlite3",
                        "test",
                    )
                    helpers._best_move(words, 0, context)
                    initial_config = helpers._search_config_key()
                    initial_database_rows = helpers.memo_store_stats()[
                        "database_rows"
                    ]

                    helpers.BUDGET = 101
                    helpers._best_move(words, 0, context)

                    self.assertTrue(helpers._BEST_MOVE_CACHE)
                    self.assertTrue(
                        all(
                            key[2:9] == helpers._search_config_key()
                            for key in helpers._BEST_MOVE_CACHE
                        )
                    )
                    self.assertNotEqual(
                        initial_config,
                        helpers._search_config_key(),
                    )
                    self.assertEqual(
                        helpers.memo_store_stats()["database_rows"],
                        initial_database_rows,
                    )
                    stored_config_count = helpers._require_memo_connection().execute(
                        "SELECT COUNT(DISTINCT config_key) FROM best_moves"
                    ).fetchone()[0]
                    self.assertEqual(stored_config_count, 1)
            finally:
                helpers.close_memo_store()
                helpers._guess_count.cache_clear()
                helpers._BEST_MOVE_CACHE.clear()
                (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
                    helpers.MAX_K,
                ) = original_settings

    def test_best_move_discards_memos_from_other_search_settings(self) -> None:
        words = ["AAAAA"]
        context = (
            words,
            {words[0]: 0},
            np.asarray([[242]], dtype=np.uint8),
            "test",
        )
        original_settings = (
            helpers.EXHAUSTIVE_LIMIT,
            helpers.BUDGET,
            helpers.FACTOR,
            helpers.MIN_K,
            helpers.ENTROPY_MARGIN,
            helpers.MAX_K,
        )
        original_cache_config = helpers._BEST_MOVE_CACHE_CONFIG

        try:
            with tempfile.TemporaryDirectory() as directory:
                helpers.configure_memo_store(
                    Path(directory) / "memo.sqlite3",
                    "test",
                )
                state_bytes = np.asarray([0], dtype=np.uint32).tobytes()
                current_key = (
                    "test",
                    0,
                    *helpers._search_config_key(),
                    state_bytes,
                )
                stale_config = (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET + 1,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
                    helpers.SEARCH_ALGORITHM_VERSION,
                    helpers.MAX_K,
                )
                stale_key = ("stale", 0, *stale_config, state_bytes)
                helpers._BEST_MOVE_CACHE[current_key] = (0, 1.0)
                helpers._BEST_MOVE_CACHE[stale_key] = (0, 1.0)
                helpers._BEST_MOVE_CACHE_CONFIG = None
                result = helpers._best_move(words, 0, context)
                helpers.close_memo_store()

            self.assertEqual(result, (0, 1.0))
            self.assertIn(current_key, helpers._BEST_MOVE_CACHE)
            self.assertNotIn(stale_key, helpers._BEST_MOVE_CACHE)
        finally:
            helpers._BEST_MOVE_CACHE.clear()
            helpers._BEST_MOVE_CACHE_CONFIG = original_cache_config
            (
                helpers.EXHAUSTIVE_LIMIT,
                helpers.BUDGET,
                helpers.FACTOR,
                helpers.MIN_K,
                helpers.ENTROPY_MARGIN,
                helpers.MAX_K,
            ) = original_settings

    def test_pruned_infinite_guess_cost_is_not_memoized(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray(
                [
                    [242, 0, 0],
                    [0, 242, 0],
                    [0, 0, 242],
                ],
                dtype=np.uint8,
            ),
            "test",
        )
        original_settings = (
            helpers.EXHAUSTIVE_LIMIT,
            helpers.BUDGET,
            helpers.FACTOR,
            helpers.MIN_K,
            helpers.ENTROPY_MARGIN,
        )

        with tempfile.TemporaryDirectory() as directory:
            word_list_path = Path(directory) / "words.txt"
            word_list_path.write_text("\n".join(words), encoding="utf-8")
            try:
                with patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    word_list_path,
                ):
                    helpers._guess_count.cache_clear()
                    helpers._BEST_MOVE_CACHE.clear()
                    helpers.EXHAUSTIVE_LIMIT = 3
                    helpers.BUDGET = 100
                    helpers.FACTOR = 4
                    helpers.MIN_K = 1
                    helpers.ENTROPY_MARGIN = 100.0
                    helpers.configure_memo_store(
                        Path(directory) / "memo.sqlite3",
                        "test",
                    )
                    state_key = (
                        "test",
                        0,
                        *helpers._search_config_key(),
                        np.asarray([0, 1, 2], dtype=np.uint32).tobytes(),
                    )

                    cost = helpers._evaluate_guess(
                        0,
                        words,
                        1.0,
                        0,
                        context,
                    )

                    self.assertEqual(cost, float("inf"))
                    self.assertNotIn(state_key, helpers._BEST_MOVE_CACHE)
                    self.assertTrue(
                        all(
                            cached_cost < float("inf")
                            for _, cached_cost in helpers._BEST_MOVE_CACHE.values()
                        )
                    )
            finally:
                helpers.close_memo_store()
                helpers._guess_count.cache_clear()
                helpers._BEST_MOVE_CACHE.clear()
                (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
                ) = original_settings

    def test_best_move_memo_persists_and_reloads_from_sqlite(self) -> None:
        words = ["AAAAA"]
        context = (
            words,
            {words[0]: 0},
            np.asarray([[242]], dtype=np.uint8),
            "test",
        )
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "memo.sqlite3"
            helpers.configure_memo_store(database_path, "test")
            first_result = helpers._best_move(words, 0, context)
            self.assertEqual(first_result, (0, 1.0))
            self.assertEqual(helpers.memo_store_stats()["database_rows"], 1)

            helpers._BEST_MOVE_CACHE.clear()
            helpers.close_memo_store()
            helpers.configure_memo_store(database_path, "test")
            with helpers.profile_search() as profile:
                resumed_result = helpers._best_move(words, 0, context)

            self.assertEqual(resumed_result, first_result)
            self.assertEqual(profile.states_computed, 0)
            self.assertEqual(profile.memo_hits, 1)
            helpers.close_memo_store()

    def test_memo_store_waits_for_a_concurrent_sqlite_writer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "memo.sqlite3"
            helpers.configure_memo_store(database_path, "test")
            writer_started = Event()

            def hold_write_lock() -> None:
                connection = sqlite3.connect(database_path)
                connection.execute("BEGIN IMMEDIATE")
                writer_started.set()
                time.sleep(0.1)
                connection.commit()
                connection.close()

            writer = Thread(target=hold_write_lock)
            writer.start()
            try:
                self.assertTrue(writer_started.wait(timeout=5))
                busy_timeout = helpers._require_memo_connection().execute(
                    "PRAGMA busy_timeout"
                ).fetchone()[0]
                self.assertEqual(
                    busy_timeout,
                    helpers.MEMO_BUSY_TIMEOUT_SECONDS * 1_000,
                )
                state_key = (
                    "test",
                    0,
                    *helpers._search_config_key(),
                    np.asarray([0], dtype=np.uint32).tobytes(),
                )
                helpers._memo_put(state_key, (0, 1.0))
            finally:
                writer.join(timeout=5)
                helpers.close_memo_store()
            self.assertFalse(writer.is_alive())

    def test_evaluate_solver_resumes_answer_results_and_reuses_context(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray(
                [
                    [242, 0, 0],
                    [0, 242, 0],
                    [0, 0, 242],
                ],
                dtype=np.uint8,
            ),
            "test",
        )
        attempt_counts = {"AAAAA": 1, "BBBBB": 2, "CCCCC": 3}

        with tempfile.TemporaryDirectory() as directory:
            helpers.configure_memo_store(
                Path(directory) / "memo.sqlite3",
                "test",
            )
            try:
                with (
                    patch.object(
                        solver,
                        "_load_answers",
                        return_value=words,
                    ) as load_answers,
                    patch.object(
                        partition_functions,
                        "DATASET_PATH",
                        Path(directory) / "answers.txt",
                    ),
                    patch.object(
                        solver,
                        "_search_context",
                        return_value=context,
                    ) as search_context,
                    patch.object(
                        solver,
                        "_simulate_game_with_context",
                        side_effect=lambda answer, all_answers, strategy, current_context, initial_guess, guess_history: (
                            (
                                guess_history.extend(
                                    [
                                        {
                                            "guess": (
                                                "BBBBB"
                                                if answer == "AAAAA"
                                                else "AAAAA"
                                            ),
                                            "feedback": "PPPPP",
                                        }
                                    ]
                                    * (attempt_counts[answer] - 1)
                                    + [
                                        {
                                            "guess": answer,
                                            "feedback": "VVVVV",
                                        }
                                    ]
                                )
                                or attempt_counts[answer]
                            )
                            if answer in all_answers
                            and strategy == "entropy"
                            and current_context is context
                            and initial_guess is None
                            else 0
                        ),
                    ) as simulate,
                    redirect_stdout(io.StringIO()),
                ):
                    first_evaluation = solver.evaluate_solver(
                        answers=words,
                        checkpoint_interval=1,
                        answer_list="solutions",
                    )
                    self.assertEqual(simulate.call_count, len(words))
                    search_context.assert_called_once()

                    simulate.reset_mock()
                    search_context.reset_mock()
                    json_path = solver._evaluation_json_path(
                        "entropy",
                        helpers.evaluation_scope_key(words),
                        "test",
                    )
                    self.assertRegex(
                        json_path.name,
                        re.compile(
                            r"^entropy_games_entropy_\d{8}_\d{6}\.json$"
                        ),
                    )
                    json_path.unlink()
                    rebuilt_evaluation = solver.evaluate_solver(
                        answers=words,
                        checkpoint_interval=1,
                        answer_list="solutions",
                    )
                    self.assertEqual(simulate.call_count, len(words))

                    simulate.reset_mock()
                    search_context.reset_mock()
                    resumed_evaluation = solver.evaluate_solver(
                        answers=words,
                        checkpoint_interval=1,
                        answer_list="solutions",
                    )

                    self.assertEqual(
                        [call.args for call in load_answers.call_args_list],
                        [("solutions",)] * 3,
                    )
                self.assertEqual(first_evaluation, rebuilt_evaluation)
                self.assertEqual(first_evaluation, resumed_evaluation)
                self.assertEqual(simulate.call_count, 0)
                search_context.assert_called_once()
                self.assertEqual(first_evaluation.total_games, len(words))
                self.assertEqual(first_evaluation.distribution, {1: 1, 2: 1, 3: 1})
            finally:
                helpers.close_memo_store()

    def test_save_evaluation_json_uses_new_checkpoint_when_target_is_locked(self) -> None:
        words = ["AAAAA"]
        evaluation_key = helpers.evaluation_scope_key(words)
        word_key = "test"

        with tempfile.TemporaryDirectory() as directory:
            results_dir = Path(directory)
            json_path = results_dir / "entropy_games_entropy_20261104_194333.json"
            json_path.write_text("existing checkpoint", encoding="utf-8")
            original_replace = Path.replace

            def replace_unless_locked(source: Path, target: Path) -> Path:
                if target == json_path:
                    raise PermissionError("target is locked")
                return original_replace(source, target)

            with (
                patch.object(Path, "replace", new=replace_unless_locked),
                patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    results_dir / "answers.txt",
                ),
                redirect_stdout(io.StringIO()),
            ):
                saved_path = solver._save_evaluation_json(
                    json_path,
                    "entropy",
                    evaluation_key,
                    word_key,
                    words,
                    {"AAAAA": 1},
                    {
                        "AAAAA": [
                            {"guess": "AAAAA", "feedback": "VVVVV"},
                        ],
                    },
                    complete=False,
                )
                resumed_path = solver._evaluation_json_path(
                    "entropy",
                    evaluation_key,
                    word_key,
                )

            self.assertNotEqual(saved_path, json_path)
            self.assertTrue(json_path.exists())
            self.assertEqual(json_path.read_text(encoding="utf-8"), "existing checkpoint")
            self.assertTrue(saved_path.exists())
            self.assertEqual(resumed_path, saved_path)
            self.assertEqual(
                len(
                    solver._load_evaluation_json(
                        saved_path,
                        "entropy",
                        evaluation_key,
                        word_key,
                    )[0]
                ),
                1,
            )

    def test_evaluate_solver_parallel_matches_serial(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC"]

        with tempfile.TemporaryDirectory() as directory:
            word_list_path = Path(directory) / "answers.txt"
            word_list_path.write_text("\n".join(words), encoding="utf-8")
            runtime_log_path = word_list_path.with_name("entropy_runtime.log")
            runtime_log_path.write_text("preexisting log entry\n", encoding="utf-8")
            try:
                with (
                    patch.object(
                        partition_functions,
                        "DATASET_PATH",
                        word_list_path,
                    ),
                    redirect_stdout(io.StringIO()),
                ):
                    serial_result = solver.evaluate_solver(
                        "entropy",
                        resume=False,
                        checkpoint_interval=1,
                        workers=1,
                    )
                    with helpers.profile_search() as profile:
                        wait_calls = 0

                        def wait_with_initial_heartbeat(
                            futures: Iterable[Future[Any]],
                            timeout: float | None = None,
                            return_when: str = "ALL_COMPLETED",
                        ) -> tuple[set[Future[Any]], set[Future[Any]]]:
                            nonlocal wait_calls
                            wait_calls += 1
                            if wait_calls == 1:
                                pending = set(futures)
                                return set(), pending
                            return futures_wait(
                                futures,
                                timeout=timeout,
                                return_when=return_when,
                            )

                        with patch.object(
                            solver,
                            "wait",
                            side_effect=wait_with_initial_heartbeat,
                        ):
                            parallel_result = solver.evaluate_solver(
                                "entropy",
                                resume=False,
                                checkpoint_interval=1,
                                workers=2,
                            )

                self.assertEqual(parallel_result, serial_result)
                self.assertEqual(parallel_result.total_games, len(words))
                self.assertEqual(profile.worker_processes, 2)
                log_lines = runtime_log_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                self.assertEqual(log_lines[0], "preexisting log entry")
                runtime_events = [
                    json.loads(line)["event"]
                    for line in log_lines[1:]
                ]
                self.assertEqual(runtime_events.count("run_started"), 2)
                self.assertEqual(runtime_events.count("run_completed"), 2)
                self.assertIn(
                    "parallel_answer_evaluation_completed",
                    runtime_events,
                )
                self.assertIn(
                    "parallel_evaluation_heartbeat",
                    runtime_events,
                )
                self.assertEqual(
                    runtime_events.count("worker_answer_completed"),
                    3,
                )
                self.assertEqual(runtime_events.count("worker_answer_started"), 3)
                self.assertEqual(runtime_events.count("worker_batch_started"), 3)
                json_files = list(Path(directory).glob("entropy_games_*.json"))
                self.assertEqual(len(json_files), 1)
                saved_results = json.loads(
                    json_files[0].read_text(encoding="utf-8")
                )
                self.assertTrue(saved_results["complete"])
                self.assertEqual(saved_results["total_games"], len(words))
                self.assertEqual(
                    [game["answer"] for game in saved_results["games"]],
                    words,
                )
                feedback_matrix, feedback_indices, _ = (
                    partition_functions._get_feedback_matrix(words)
                )
                for game in saved_results["games"]:
                    self.assertEqual(len(game["guesses"]), game["attempts"])
                    self.assertEqual(game["guesses"][-1]["guess"], game["answer"])
                    self.assertEqual(game["guesses"][-1]["feedback"], "VVVVV")
                    answer_index = feedback_indices[game["answer"]]
                    for step in game["guesses"]:
                        guess_index = feedback_indices[step["guess"]]
                        self.assertEqual(
                            step["feedback"],
                            solver._feedback_text(
                                int(feedback_matrix[guess_index, answer_index])
                            ),
                        )
                self.assertIn("summary", saved_results)
            finally:
                helpers.close_memo_store()
                key = partition_functions._words_key(words)
                matrix = partition_functions._FEEDBACK_MATRIX_CACHE.pop(
                    key,
                    None,
                )
                if matrix is not None and getattr(matrix, "_mmap", None) is not None:
                    matrix._mmap.close()
                partition_functions._WORD_INDEX_CACHE.pop(key, None)
                partition_functions._MATRIX_VALIDATED.discard(key)

    def test_best_move_parallel_root_matches_serial(self) -> None:
        words = random.Random(2026).sample(solver._load_answers(), 12)

        with tempfile.TemporaryDirectory() as directory:
            parallel_path = Path(directory) / "parallel_answers.txt"
            serial_path = Path(directory) / "serial_answers.txt"
            word_content = "\n".join(words)
            parallel_path.write_text(word_content, encoding="utf-8")
            serial_path.write_text(word_content, encoding="utf-8")
            try:
                with patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    parallel_path,
                ):
                    with helpers.profile_search() as profile:
                        with redirect_stdout(io.StringIO()) as progress_output:
                            parallel_result = solver.best_move(words, workers=2)
                    helpers.close_memo_store()
                self.assertEqual(profile.worker_processes, 2)
                self.assertIn("palpite base", progress_output.getvalue())
                self.assertIn("grupos recursivos", progress_output.getvalue())
                self.assertIn("distribuindo os", progress_output.getvalue())
                self.assertIn("grupo ", progress_output.getvalue())
                self.assertIn("palpite ", progress_output.getvalue())
                self.assertNotIn("Ainda avaliando", progress_output.getvalue())
                self.assertNotIn("ainda em andamento", progress_output.getvalue())
                self.assertNotIn("workers ainda avaliando", progress_output.getvalue())

                helpers._BEST_MOVE_CACHE.clear()
                with patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    serial_path,
                ):
                    serial_result = solver.best_move(words)

                self.assertEqual(parallel_result, serial_result)
            finally:
                helpers.close_memo_store()
                helpers._BEST_MOVE_CACHE.clear()
                key = partition_functions._words_key(words)
                matrix = partition_functions._FEEDBACK_MATRIX_CACHE.pop(
                    key,
                    None,
                )
                if matrix is not None and getattr(matrix, "_mmap", None) is not None:
                    matrix._mmap.close()
                partition_functions._WORD_INDEX_CACHE.pop(key, None)
                partition_functions._MATRIX_VALIDATED.discard(key)

    def test_base_guess_reports_at_recursive_feedback_group_interval(self) -> None:
        words = ["SORIA"]
        context = (
            words,
            {"SORIA": 0},
            np.zeros((1, 1), dtype=np.uint8),
            "test",
        )
        output = io.StringIO()

        def evaluate_with_progress(*args, **kwargs) -> float:
            self.assertEqual(len(args), 5)
            callback = kwargs["group_progress_callback"]
            for _ in range(200):
                callback()
            return 1.0

        with patch.object(solver, "_GROUP_PROGRESS_INTERVAL", 100):
            with patch.object(
                helpers,
                "_evaluate_guess",
                side_effect=evaluate_with_progress,
            ):
                with redirect_stdout(output):
                    result = solver._parallel_root_evaluator(
                        words,
                        [0],
                        0,
                        context,
                        4,
                    )

        self.assertEqual(result, (0, 1.0))
        progress_lines = [
            line for line in output.getvalue().splitlines()
            if "grupos de feedback recursivos concluídos" in line
        ]
        self.assertEqual(len(progress_lines), 2)
        self.assertIn("100 grupos", progress_lines[0])
        self.assertIn("200 grupos", progress_lines[1])

    def test_evaluate_guess_reports_completed_recursive_groups(self) -> None:
        words = ["AAAAA", "BBBBB", "CCCCC"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray(
                [[0, 1, 2], [0, 0, 0], [0, 0, 0]],
                dtype=np.uint8,
            ),
            "test",
        )
        completed_groups: list[None] = []
        callback = lambda: completed_groups.append(None)

        with patch.object(helpers, "_best_move", return_value=(0, 1.0)) as best_move:
            cost = helpers._evaluate_guess(
                0,
                words,
                float("inf"),
                0,
                context,
                group_progress_callback=callback,
            )

        self.assertTrue(np.isfinite(cost))
        self.assertEqual(len(completed_groups), 3)
        self.assertEqual(best_move.call_count, 3)
        self.assertTrue(
            all(
                call.kwargs["group_progress_callback"] is callback
                for call in best_move.call_args_list
            )
        )

    def test_evaluate_solver_rejects_non_positive_worker_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "workers must be greater than zero"):
            solver.evaluate_solver(workers=0)

    def test_in_memory_memo_respects_configured_size_limit(self) -> None:
        original_limit = helpers.MEMO_MEMORY_LIMIT
        original_cache = helpers._BEST_MOVE_CACHE.copy()
        try:
            helpers._BEST_MOVE_CACHE.clear()
            helpers.MEMO_MEMORY_LIMIT = 2
            config = helpers._search_config_key()
            for index in range(3):
                state_key = (
                    "test",
                    0,
                    *config,
                    np.asarray([index], dtype=np.uint32).tobytes(),
                )
                helpers._remember_state(state_key, (index, 1.0))

            self.assertEqual(len(helpers._BEST_MOVE_CACHE), 2)
            self.assertEqual(
                [key[-1] for key in helpers._BEST_MOVE_CACHE],
                [
                    np.asarray([1], dtype=np.uint32).tobytes(),
                    np.asarray([2], dtype=np.uint32).tobytes(),
                ],
            )
        finally:
            helpers._BEST_MOVE_CACHE.clear()
            helpers._BEST_MOVE_CACHE.update(original_cache)
            helpers.MEMO_MEMORY_LIMIT = original_limit

    def test_deep_cost_matches_evaluation_on_seeded_word_sample(self) -> None:
        original_path = partition_functions.DATASET_PATH
        original_settings = (
            helpers.EXHAUSTIVE_LIMIT,
            helpers.BUDGET,
            helpers.FACTOR,
            helpers.MIN_K,
            helpers.ENTROPY_MARGIN,
        )
        source_words = solver._load_answers()
        words = random.Random(7341).sample(source_words, 18)

        with tempfile.TemporaryDirectory() as directory:
            word_list_path = Path(directory) / "answers.txt"
            word_list_path.write_text("\n".join(words), encoding="utf-8")
            try:
                with patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    word_list_path,
                ):
                    helpers.EXHAUSTIVE_LIMIT = 30
                    helpers.BUDGET = 1_000_000
                    helpers.FACTOR = 4
                    helpers.MIN_K = 5
                    helpers.ENTROPY_MARGIN = 1.0
                    guess_index, expected_cost = solver.best_move(words)
                    result = solver.evaluate_solver(
                        "groups",
                        checkpoint_interval=5,
                    )

                    self.assertGreaterEqual(guess_index, 0)
                    self.assertAlmostEqual(
                        expected_cost,
                        result.average_attempts,
                    )
                    self.assertEqual(result.total_games, len(words))
                    self.assertLessEqual(
                        result.worst_case,
                        helpers.MAX_ATTEMPTS,
                    )

                    helpers.EXHAUSTIVE_LIMIT = 5
                    helpers.BUDGET = 20
                    helpers.MIN_K = 1
                    bounded_guess, bounded_cost = solver.best_move(words)
                    bounded_result = solver.evaluate_solver(
                        "groups",
                        resume=False,
                        checkpoint_interval=6,
                    )

                    self.assertGreaterEqual(bounded_guess, 0)
                    self.assertGreaterEqual(
                        bounded_cost + 1e-12,
                        expected_cost,
                    )
                    self.assertAlmostEqual(
                        bounded_cost,
                        bounded_result.average_attempts,
                    )
                    self.assertLessEqual(
                        bounded_result.worst_case,
                        helpers.MAX_ATTEMPTS,
                    )
            finally:
                helpers.close_memo_store()
                key = partition_functions._words_key(words)
                matrix = partition_functions._FEEDBACK_MATRIX_CACHE.pop(
                    key,
                    None,
                )
                if matrix is not None and getattr(matrix, "_mmap", None) is not None:
                    matrix._mmap.close()
                partition_functions._WORD_INDEX_CACHE.pop(key, None)
                partition_functions._MATRIX_VALIDATED.discard(key)
                helpers._BEST_MOVE_CACHE.clear()
                helpers._guess_count.cache_clear()
                for matrix_path in word_list_path.parent.glob("feedback_matrix_*.npy"):
                    matrix_path.unlink()
                first_guess_path = word_list_path.with_name(
                    "entropy_first_guess.json"
                )
                if first_guess_path.exists():
                    first_guess_path.unlink()
                database_path = word_list_path.with_name("entropy_memo.sqlite3")
                if database_path.exists():
                    database_path.unlink()
                partition_functions.DATASET_PATH = original_path
                (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
                ) = original_settings


if __name__ == "__main__":
    unittest.main()
