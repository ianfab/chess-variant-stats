import unittest
import numpy as np
import pandas as pd

import piece_values


class TestPieceValues(unittest.TestCase):
    def test_imbalance(self):
        # single piece
        self.assertTrue(piece_values.has_imbalance(['K', 'Q', 'k', 'r'], 'Qr'))
        self.assertTrue(piece_values.has_imbalance(['K', 'Q', 'R', 'k', 'r', 'r'], 'Qr'))
        self.assertTrue(piece_values.has_imbalance(['K', 'Q', 'Q', 'k', 'r', 'r'], 'Qr'))
        self.assertFalse(piece_values.has_imbalance(['K', 'Q', 'k'], 'Qr'))
        self.assertFalse(piece_values.has_imbalance(['K', 'Q', 'k', 'r'], 'Rq'))
        self.assertFalse(piece_values.has_imbalance(['K', 'Q', 'R', 'k', 'r'], 'Qr'))
        # multi-piece
        self.assertTrue(piece_values.has_imbalance(['K', 'Q', 'k', 'r', 'r'], 'Qrr'))
        self.assertFalse(piece_values.has_imbalance(['K', 'Q', 'R', 'k', 'r', 'r'], 'Qrr'))

    def test_game_phase(self):
        self.assertEqual(piece_values.game_phase(2, 32, 17), 0)
        self.assertEqual(piece_values.game_phase(2, 32, 16), 1)

    def test_estimate_uncertainty_bootstrap(self):
        # Create synthetic test data
        np.random.seed(42)
        n_samples = 50
        
        # Create piece difference data
        piece_diffs = pd.DataFrame({
            'q': np.random.normal(0, 1, n_samples),
            'r': np.random.normal(0, 1, n_samples),
            'n': np.random.normal(0, 1, n_samples)
        })
        
        # Create results based on piece differences (with some noise)
        true_values = {'q': 9, 'r': 5, 'n': 3}
        logits = sum(piece_diffs[p] * true_values[p] for p in piece_diffs.columns)
        probs = 1 / (1 + np.exp(-logits))
        results = [1 if p > 0.5 else 0 for p in probs]
        
        # Test bootstrap uncertainty estimation
        coef_mean, coef_std, intercept_mean, intercept_std = piece_values.estimate_uncertainty_bootstrap(
            piece_diffs, results, n_bootstrap=10, random_state=42)
        
        # Check that uncertainties are reasonable
        self.assertIsNotNone(coef_mean)
        self.assertIsNotNone(coef_std)
        self.assertIsNotNone(intercept_std)
        
        # Standard errors should be positive
        self.assertTrue(all(std > 0 for std in coef_std))
        self.assertTrue(intercept_std > 0)
        
        # Check dimensions
        self.assertEqual(len(coef_std), len(piece_diffs.columns))

    def test_estimate_uncertainty_bootstrap_insufficient_data(self):
        # Test with insufficient data
        piece_diffs = pd.DataFrame({'q': [1, -1], 'r': [0, 1]})
        results = [1, 0]
        
        coef_mean, coef_std, intercept_mean, intercept_std = piece_values.estimate_uncertainty_bootstrap(
            piece_diffs, results, n_bootstrap=10)
        
        # Should return None for insufficient data
        self.assertIsNone(coef_std)
        self.assertIsNone(intercept_std)


if __name__ == '__main__':
    unittest.main()
