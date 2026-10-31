from contextlib import redirect_stdout
import csv
import io
import random
import statistics
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from algorithm.inclusive import algorithm as inclusive
from algorithm.inclusive import functions as inclusive_functions
from algorithm.partition import algorithm as partition
from algorithm import functions as f
from algorithm import termo_implementation as t
import main


class AlgorithmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.words = f.file_to_list(str(partition.DATASET_PATH))

    def test_consistent_filter_matches_scoring_definition(self) -> None:
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
                inclusive_functions.consistent_filter(
                    self.words,
                    guess,
                    feedback,
                ),
                expected,
            )

    def test_arroz_rapaz_exact_filter_has_three_candidates(self) -> None:
        feedback = t.score_guess("RAPAZ", "ARROZ")
        candidates = inclusive_functions.consistent_filter(
            self.words,
            "ARROZ",
            feedback,
        )
        self.assertEqual(len(candidates), 3)
        self.assertIn("RAPAZ", candidates)

    def test_feedback_matrix_matches_score_guess_on_3000_pairs(self) -> None:
        matrix, index, key = partition._get_feedback_matrix(self.words)
        self.assertIn(key, partition._MATRIX_VALIDATED)
        rng = random.Random(0)
        for _ in range(3000):
            guess = rng.choice(self.words)
            answer = rng.choice(self.words)
            expected = partition._feedback_code(t.score_guess(answer, guess))
            self.assertEqual(int(matrix[index[guess], index[answer]]), expected)

    def test_matrix_filter_matches_consistent_filter_for_500_pairs(self) -> None:
        matrix, index, _key = partition._get_feedback_matrix(self.words)
        rng = random.Random(11)
        all_indices = list(range(len(self.words)))
        for _ in range(500):
            guess = rng.choice(self.words)
            answer = rng.choice(self.words)
            feedback = t.score_guess(answer, guess)
            feedback_code = partition._feedback_code(feedback)
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
                inclusive_functions.consistent_filter(
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
        matrix, index, word_key = partition._get_feedback_matrix(words)
        first_guess_index = partition._choose_partition_guess(
            list(range(len(words))),
            set(),
            matrix,
            word_key,
        )
        answer = next(word for word in words if index[word] != first_guess_index)
        first_guess = words[first_guess_index]
        feedback_code = partition._feedback_code(t.score_guess(answer, first_guess))
        possible_indices = np.flatnonzero(
            matrix[first_guess_index, :] == feedback_code
        ).tolist()
        override_index = next(
            guess_index
            for guess_index in range(len(words))
            if guess_index != first_guess_index
        )
        override_key = word_key, partition._candidate_state_key(possible_indices)
        output = io.StringIO()

        with patch.dict(
            partition._BOUNDED_GUESS_OVERRIDES,
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
        first_guess_index = partition._FIRST_GUESS_CACHE[
            partition._words_key(self.words)
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

    def test_main_preserves_csv_columns(self) -> None:
        words = ["PATOS", "FATOS", "GATOS"]
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "results.csv"
            main.run_all_answers(
                words,
                output_path,
                max_workers=2,
                batch_size=2,
            )
            with output_path.open(encoding="utf-8", newline="") as file:
                reader = csv.reader(file)
                self.assertEqual(
                    next(reader),
                    ["answer", "algorithm", "word_function", "attempts", "solved"],
                )
                rows = list(reader)
        self.assertEqual(len(rows), len(words))
        self.assertEqual({row[2] for row in rows}, {"partition_p2_bounded"})
        self.assertTrue(all(row[1] == "partition" for row in rows))
        self.assertTrue(all(row[-1] == "True" for row in rows))

    def test_main_reports_expected_solver_errors_as_unsolved(self) -> None:
        for error_type in (RuntimeError, AssertionError, ValueError):
            def failing_algorithm(
                *_args: object,
                _error: type[Exception] = error_type,
                **_kwargs: object,
            ) -> int:
                raise _error("expected failure")

            attempts, solved = main.run_algorithm_and_check(
                self.words,
                "PATOS",
                failing_algorithm,
                lambda candidates: candidates[0],
            )
            self.assertEqual((attempts, solved), (-1, False))


if __name__ == "__main__":
    unittest.main()
