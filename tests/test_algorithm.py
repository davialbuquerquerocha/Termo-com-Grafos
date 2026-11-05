from contextlib import redirect_stdout
import io
import json
import random
import statistics
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from algorithm.inclusive import algorithm as inclusive
from algorithm.inclusive import evaluation as inclusive_evaluation
from algorithm.partition import algorithm as partition
from algorithm.partition import evaluation as partition_evaluation
from algorithm.partition import functions as partition_functions
from algorithm import functions as f
from algorithm import termo_implementation as t
import main


class AlgorithmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.words = f.file_to_list(str(partition_functions.DATASET_PATH))

    def test_feedback_filter_matches_scoring_definition(self) -> None:
        rng = random.Random(11)
        for _ in range(500):
            guess = rng.choice(self.words)
            answer = rng.choice(self.words)
            feedback = t.score_guess(answer, guess)
            expected = [
                word for word in self.words
                if t.score_guess(word, guess) == feedback
            ]
            self.assertEqual(
                f.filter_words_by_feedback(
                    self.words,
                    guess,
                    feedback,
                ),
                expected,
            )

    def test_arroz_rapaz_exact_filter_has_three_candidates(self) -> None:
        feedback = t.score_guess("RAPAZ", "ARROZ")
        candidates = f.filter_words_by_feedback(
            self.words,
            "ARROZ",
            feedback,
        )
        self.assertEqual(len(candidates), 3)
        self.assertIn("RAPAZ", candidates)

    def test_accented_words_use_accent_insensitive_feedback_matrix(self) -> None:
        words = ["AUDIO", "ÁUDIO", "RADIO"]

        with tempfile.TemporaryDirectory() as directory:
            word_list_path = Path(directory) / "words.txt"
            word_list_path.write_text("\n".join(words), encoding="utf-8")
            key: str | None = None
            try:
                with patch.object(
                    partition_functions,
                    "DATASET_PATH",
                    word_list_path,
                ):
                    matrix, index, key = partition_functions._get_feedback_matrix(
                        words
                    )

                    self.assertEqual(
                        t.score_guess("ÁUDIO", "AUDIO")[2],
                        [("A", 1), ("U", 2), ("D", 3), ("I", 4), ("O", 5)],
                    )
                    self.assertEqual(
                        t.evaluate_guess("ÁUDIO", "AUDIO", {"AUDIO"})[2],
                        [("A", 1), ("U", 2), ("D", 3), ("I", 4), ("O", 5)],
                    )
                    for guess in words:
                        for answer in words:
                            expected = partition_functions._feedback_code(
                                t.score_guess(answer, guess)
                            )
                            self.assertEqual(
                                int(matrix[index[guess], index[answer]]),
                                expected,
                            )
            finally:
                if key is not None:
                    matrix = partition_functions._FEEDBACK_MATRIX_CACHE.pop(
                        key,
                        None,
                    )
                    if matrix is not None and getattr(matrix, "_mmap", None) is not None:
                        matrix._mmap.close()
                    partition_functions._WORD_INDEX_CACHE.pop(key, None)
                    partition_functions._MATRIX_VALIDATED.discard(key)

    def test_feedback_matrix_matches_score_guess_on_3000_pairs(self) -> None:
        matrix, index, key = partition_functions._get_feedback_matrix(self.words)
        self.assertIn(key, partition_functions._MATRIX_VALIDATED)
        rng = random.Random(0)
        for _ in range(3000):
            guess = rng.choice(self.words)
            answer = rng.choice(self.words)
            expected = partition_functions._feedback_code(
                t.score_guess(answer, guess)
            )
            self.assertEqual(int(matrix[index[guess], index[answer]]), expected)

    def test_matrix_filter_matches_general_feedback_filter_for_500_pairs(self) -> None:
        matrix, index, _key = partition_functions._get_feedback_matrix(self.words)
        rng = random.Random(11)
        all_indices = list(range(len(self.words)))
        for _ in range(500):
            guess = rng.choice(self.words)
            answer = rng.choice(self.words)
            feedback = t.score_guess(answer, guess)
            feedback_code = partition_functions._feedback_code(feedback)
            matching_indices = [
                candidate_index
                for candidate_index in all_indices
                if matrix[index[guess], candidate_index] == feedback_code
            ]
            matrix_candidates = {
                self.words[candidate_index]
                for candidate_index in matching_indices
            }
            filtered_candidates = set(
                f.filter_words_by_feedback(
                    self.words,
                    guess,
                    feedback,
                )
            )
            self.assertEqual(matrix_candidates, filtered_candidates)

    def test_partition_solver_uses_unique_guesses_and_preserves_answer(self) -> None:
        words = ["PATOS", "FATOS", "GATOS", "JATOS", "NATOS", "RATOS", "MATOS"]
        output = io.StringIO()
        with redirect_stdout(output):
            attempts = partition.partition_algorithm(
                words,
                "PATOS",
                lambda _candidates: self.fail("word_function must be ignored"),
                show_progress=True,
            )

        guessed = [
            line.removeprefix("Guess: ")
            for line in output.getvalue().splitlines()
            if line.startswith("Guess: ")
        ]
        self.assertLessEqual(attempts, 5)
        self.assertEqual(len(guessed), len(set(guessed)))

    def test_partition_solver_uses_prepared_bounded_override(self) -> None:
        words = ["PATOS", "FATOS", "GATOS", "JATOS", "NATOS", "RATOS", "MATOS"]
        matrix, index, word_key = partition_functions._get_feedback_matrix(words)
        first_guess_index = partition_functions._choose_partition_guess(
            list(range(len(words))),
            set(),
            matrix,
            word_key,
        )
        answer = next(word for word in words if index[word] != first_guess_index)
        first_guess = words[first_guess_index]
        feedback_code = partition_functions._feedback_code(
            t.score_guess(answer, first_guess)
        )
        possible_indices = np.flatnonzero(
            matrix[first_guess_index, :] == feedback_code
        ).tolist()
        override_index = next(
            guess_index
            for guess_index in range(len(words))
            if guess_index != first_guess_index
        )
        override_key = (
            word_key,
            partition_functions._candidate_state_key(possible_indices),
        )
        output = io.StringIO()

        with patch.dict(
            partition_functions._BOUNDED_GUESS_OVERRIDES,
            {override_key: override_index},
        ), redirect_stdout(output):
            partition.partition_algorithm(
                words,
                answer,
                lambda _candidates: self.fail("word_function must be ignored"),
                show_progress=True,
            )

        guesses = [
            line.removeprefix("Guess: ")
            for line in output.getvalue().splitlines()
            if line.startswith("Guess: ")
        ]
        self.assertEqual(guesses[1], words[override_index])

    def test_partition_solver_quality_on_seeded_sample(self) -> None:
        rng = random.Random(11)
        answers = rng.sample(self.words, 1500)
        attempts = [
            partition.partition_algorithm(
                self.words,
                answer,
                lambda _candidates: self.fail("word_function must be ignored"),
                show_progress=False,
            )
            for answer in answers
        ]
        self.assertLessEqual(statistics.mean(attempts), 4.2)
        self.assertLessEqual(sum(value > 6 for value in attempts), 15)
        self.assertLessEqual(max(attempts), 8)
        first_guess_index = partition_functions._FIRST_GUESS_CACHE[
            partition_functions._words_key(self.words)
        ]
        self.assertEqual(self.words[first_guess_index], "SORIA")

    def test_inclusive_solver_is_in_its_own_module(self) -> None:
        words = ["PATOS", "FATOS", "GATOS"]
        attempts = inclusive.inclusive_algorithm(
            words,
            "PATOS",
            lambda _candidates: "PATOS",
            show_progress=False,
        )
        self.assertEqual(attempts, 1)

    def test_inclusive_evaluation_writes_json_with_guess_history(self) -> None:
        words = ["PATOS", "FATOS", "GATOS"]
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "inclusive.json"
            processed, simulations = inclusive_evaluation.run_all_answers(
                words,
                output_path,
                heuristic="frequency",
                max_workers=2,
            )
            results = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual((processed, simulations), (3, 3))
        self.assertEqual(results["algorithm"], "inclusive")
        self.assertEqual(results["settings"]["heuristic"], "frequency")
        self.assertTrue(results["complete"])
        self.assertEqual(results["completed_games"], len(words))
        self.assertEqual(len(results["games"]), len(words))
        for game in results["games"]:
            self.assertTrue(game["solved"])
            self.assertEqual(game["attempts"], len(game["guesses"]))
            self.assertEqual(game["guesses"][-1]["guess"], game["answer"])
            self.assertEqual(game["guesses"][-1]["feedback"], "VVVVV")

    def test_partition_evaluation_writes_json_with_guess_history(self) -> None:
        words = ["PATOS", "FATOS", "GATOS"]
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results.json"
            processed, simulations = partition_evaluation.run_all_answers(
                words,
                output_path,
                max_workers=1,
                batch_size=2,
            )
            results = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual((processed, simulations), (3, 3))
        self.assertEqual(results["algorithm"], "partition")
        self.assertTrue(results["complete"])
        self.assertEqual(results["completed_games"], len(words))
        self.assertEqual(len(results["games"]), len(words))
        for game in results["games"]:
            self.assertTrue(game["solved"])
            self.assertEqual(game["attempts"], len(game["guesses"]))
            self.assertEqual(game["guesses"][-1]["guess"], game["answer"])
            self.assertEqual(game["guesses"][-1]["feedback"], "VVVVV")

    def test_main_dispatches_entropy_arguments(self) -> None:
        with patch("algorithm.entropy.algorithm.main") as entropy_main:
            main.main(
                ["entropy", "simulate", "TERMO", "--strategy", "groups"]
            )

        entropy_main.assert_called_once_with(
            ["simulate", "TERMO", "--strategy", "groups"]
        )

    def test_main_partition_cli_options(self) -> None:
        words = ["PATOS", "FATOS", "GATOS"]
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "custom.json"
            with (
                patch.object(
                    partition_evaluation.f,
                    "file_to_list",
                    return_value=words,
                ),
                patch.object(
                    partition_evaluation,
                    "run_all_answers",
                    return_value=(3, 3),
                ) as run,
            ):
                partition_evaluation.main(
                    [
                        "--workers",
                        "2",
                        "--batch-size",
                        "3",
                        "--output",
                        str(output_path),
                    ]
                )

        run.assert_called_once_with(
            words,
            output_path,
            max_workers=2,
            batch_size=3,
        )

    def test_main_dispatches_partition_arguments(self) -> None:
        with patch("algorithm.partition.evaluation.main") as partition_main:
            main.main(
                ["partition", "evaluate", "--workers", "2"]
            )

        partition_main.assert_called_once_with(["--workers", "2"])

    def test_main_dispatches_inclusive_arguments(self) -> None:
        with patch("algorithm.inclusive.evaluation.main") as inclusive_main:
            main.main(
                ["inclusive", "--heuristic", "frequency", "--workers", "1"]
            )

        inclusive_main.assert_called_once_with(
            ["--heuristic", "frequency", "--workers", "1"]
        )

    def test_main_defaults_to_partition_launcher(self) -> None:
        with patch("algorithm.partition.evaluation.main") as partition_main:
            main.main([])

        partition_main.assert_called_once_with([])

    def test_main_reports_expected_solver_errors_as_unsolved(self) -> None:
        for error_type in (RuntimeError, AssertionError, ValueError):
            def failing_algorithm(
                *_args: object,
                _error: type[Exception] = error_type,
                **_kwargs: object,
            ) -> int:
                raise _error("expected failure")

            attempts, solved = partition_evaluation.run_algorithm_and_check(
                self.words,
                "PATOS",
                failing_algorithm,
                lambda candidates: candidates[0],
            )
            self.assertEqual((attempts, solved), (-1, False))


if __name__ == "__main__":
    unittest.main()
