import argparse
from collections import defaultdict, Counter
import fileinput

import numpy as np
import pyffish as sf
from tqdm import tqdm

from common import sum_line_count, parse_epd


def game_stats(instream, variant, calculate_branching_factor):
    total = sum_line_count(instream)
    game_length = defaultdict(int)
    results = defaultdict(int)
    piece_frequencies = Counter()
    branching_factor = []
    mobility = []
    variants = sf.variants()
    for epd in tqdm(instream, total=total):
        fen, annotations = parse_epd(epd)
        current_variant = annotations.get('variant', variant)
        if not current_variant:
            raise Exception('Variant neither provided in EPD nor as argument')
        elif current_variant not in variants:
            raise Exception('Variant {} not supported'.format(current_variant))
        game = annotations.get('game')
        if game:
            game_length[game] = max(game_length[game], int(fen.split(' ')[-1]))
            result = annotations.get('result')
            if result:
                results[result] += 1

        # Count occurrences of each piece type
        board_state = fen.split()[0]
        pieces = 0
        stm_pieces = 0
        for char in board_state:
            if char.isalpha():
                pieces += 1
                piece_frequencies[char] += 1
                if (fen.split()[1] == 'w') == char.isupper():
                    stm_pieces += 1

        if calculate_branching_factor:
            bf = len(sf.legal_moves(current_variant, fen, []))
            branching_factor.append(bf)
            if stm_pieces:
                mobility.append(bf / stm_pieces)

    # Calculate game tree complexity
    game_tree_complexity = None
    if branching_factor and game_length:
        avg_branching_factor = np.mean(branching_factor)
        avg_game_length = np.mean(list(game_length.values()))
        game_tree_complexity = avg_branching_factor ** avg_game_length

    def stats(v):
        return 'Median: {}\nMean: {:.1f}\nMax: {}'.format(np.median(v), np.mean(v), max(v)) if v else 'No data'
    print('\n# Results')
    if results:
        for result, count in sorted(results.items(), key=lambda x: x[0][-1]):
            print('{}: {:.2%}'.format(result, count / sum(results.values())))
    else:
        print('No data')

    print('\n# Game length')
    print(stats(list(game_length.values())))

    print('\n# Branching factor')
    print(stats(branching_factor))

    print('\n# Mobility per piece')
    print(stats(mobility))

    print('\n# Game tree complexity')
    if game_tree_complexity is not None:
        print('Estimated: {:.2e}'.format(game_tree_complexity))
    else:
        print('No data (requires branching factor calculation)')

    print('\n# Piece Frequency')
    print(f'All: {sum(piece_frequencies.values()) / total}')
    for piece, count in sorted(piece_frequencies.items(), key=lambda x: x[1], reverse=True):
        print(f'{piece}: {count / total}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-v', '--variant', help='only required if not annotated in input FEN/EPD')
    parser.add_argument('-c', '--configuration', help='variant configuration path')
    parser.add_argument('-b', '--branching-factor', action='store_true', help='calculate branching factor. Slow.')
    args = parser.parse_args()
    if args.configuration:
        sf.set_option("VariantPath", args.configuration)

    with fileinput.input(args.epd_files) as instream:
        game_stats(instream, args.variant, args.branching_factor)
