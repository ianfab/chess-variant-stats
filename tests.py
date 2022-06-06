import unittest

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


if __name__ == '__main__':
    unittest.main()
