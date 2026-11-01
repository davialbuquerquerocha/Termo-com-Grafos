from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from algorithm.entropy import algorithm as solver
from algorithm.entropy import functions as helpers
from algorithm.partition import functions as partition_functions


class EntropyAlgorithmTests(unittest.TestCase):
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

                    helpers.EXHAUSTIVE_LIMIT = 4
                    exhaustive = helpers._rank_state(
                        [*words[:3], words[4]],
                        0,
                        context,
                    )
                    self.assertEqual(set(exhaustive), set(range(len(words))))
            finally:
                helpers._guess_count.cache_clear()
                (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
                ) = original_settings

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

    def test_simulation_increments_search_depth_after_each_guess(self) -> None:
        words = ["AAAAA", "BBBBB"]
        context = (
            words,
            {word: index for index, word in enumerate(words)},
            np.asarray([[242, 0], [0, 242]], dtype=np.uint8),
            "test",
        )
        with (
            patch.object(solver, "_load_answers", return_value=words),
            patch.object(solver, "_search_context", return_value=context),
            patch.object(solver, "choose_first_guess", return_value=(0, 1.5)),
            patch.object(solver, "choose_guess", return_value=1) as choose_guess,
        ):
            attempts = solver.simulate_game("BBBBB", "deep")

        self.assertEqual(attempts, 2)
        choose_guess.assert_called_once_with(["BBBBB"], "deep", 1)

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
                    helpers._best_move(words, 0, context)
                    initial_config = helpers._search_config_key()

                    helpers.BUDGET = 101
                    helpers._best_move(words, 0, context)

                    self.assertTrue(helpers._BEST_MOVE_CACHE)
                    self.assertTrue(
                        all(
                            key[2:7] == helpers._search_config_key()
                            for key in helpers._BEST_MOVE_CACHE
                        )
                    )
                    self.assertNotEqual(
                        initial_config,
                        helpers._search_config_key(),
                    )
            finally:
                helpers._guess_count.cache_clear()
                helpers._BEST_MOVE_CACHE.clear()
                (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
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
        )
        original_cache_config = helpers._BEST_MOVE_CACHE_CONFIG

        try:
            helpers._BEST_MOVE_CACHE.clear()
            helpers._BEST_MOVE_CACHE_CONFIG = None
            current_key = (
                "current",
                0,
                *helpers._search_config_key(),
                tuple(words),
            )
            stale_config = (
                helpers.EXHAUSTIVE_LIMIT,
                helpers.BUDGET + 1,
                helpers.FACTOR,
                helpers.MIN_K,
                helpers.ENTROPY_MARGIN,
            )
            stale_key = ("stale", 0, *stale_config, tuple(words))
            helpers._BEST_MOVE_CACHE[current_key] = (0, 1.0)
            helpers._BEST_MOVE_CACHE[stale_key] = (0, 1.0)

            result = helpers._best_move(words, 0, context)

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
                    state_key = (
                        "test",
                        0,
                        *helpers._search_config_key(),
                        tuple(sorted(words)),
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
                helpers._guess_count.cache_clear()
                helpers._BEST_MOVE_CACHE.clear()
                (
                    helpers.EXHAUSTIVE_LIMIT,
                    helpers.BUDGET,
                    helpers.FACTOR,
                    helpers.MIN_K,
                    helpers.ENTROPY_MARGIN,
                ) = original_settings


if __name__ == "__main__":
    unittest.main()
