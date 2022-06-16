import argparse
from collections import defaultdict
import fileinput

import numpy as np
import pyffish as sf
from tqdm import tqdm

from common import sum_line_count, parse_epd


def game_stats(instream, variant, calculate_branching_factor):
    total = sum_line_count(instream)
    game_length = defaultdict(int)
    results = defaultdict(int)
    branching_factor = []
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
        if calculate_branching_factor:
            branching_factor.append(len(sf.legal_moves(current_variant, fen, [])))
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
