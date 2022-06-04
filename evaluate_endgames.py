import argparse
from collections import defaultdict
import fileinput
from functools import partial
import math
import re

from tqdm import tqdm


def line_count(filename):
    f = open(filename, 'rb')
    bufgen = iter(partial(f.raw.read, 1024*1024), b'')
    return sum(buf.count(b'\n') for buf in bufgen)


WLD = {'1-0': 0, '0-1': 1, '1/2-1/2': 2}


def swap_colors(pieces):
    pieces = sorted(pieces)
    black = sum(map(str.islower, ''.join(pieces)))
    white = sum(map(str.isupper, ''.join(pieces)))
    if black > white:
        return True
    elif black == white and ''.join(p for p in pieces if p.islower()) > ''.join(p for p in pieces if p.isupper()).lower():
        return True
    else:
        return False


def get_entropy(wld):
    """Calculates information theoretical entropy"""
    norm = sum(wld)
    wld = [i for i in wld if i > 0]
    return -sum(math.log2(p / norm) * p / norm for p in wld)


def evaluate_endgames(instream, variant, max_pieces, stable_ply, keep_color,
                      min_entropy, min_frequency, min_relevance, order_by, ignore_promotion):
    # Before the first line has been read, filename() returns None.
    if instream.filename() is None:
        filename = instream._files[0]
    else:
        filename = instream.filename()
    # When reading from sys.stdin, filename() is "-"
    total = None if (filename == "-") else line_count(filename)

    endgames = defaultdict(int)
    results = defaultdict(lambda: [0, 0, 0])
    piece_score = defaultdict(lambda: [0, 0, 0])
    for epd in tqdm(instream, total=total):
        tokens = epd.strip().split(';')
        fen = tokens[0]
        annotations = dict(token.split(' ', 1) for token in tokens[1:])
        current_variant = annotations.get('variant', variant)
        if not current_variant:
            raise Exception('Variant neither provided in EPD nor as argument')
        board = fen.split(' ')[0]
        pieces = re.findall(r'[A-Za-z]' if ignore_promotion else r'(?:\+)?[A-Za-z]', board)
        result = annotations.get('result')
        # swap piece and result color
        if not keep_color and swap_colors(pieces):
            pieces = [s.swapcase() for s in pieces]
            if result in ('1-0', '0-1'):
                result = '1-0' if result == '0-1' else '0-1'
        pieces = tuple(sorted(pieces))
        if len(pieces) <= max_pieces and int(annotations.get('hmvc', 0)) >= stable_ply:
            endgames[pieces] += 1
            if result:
                results[pieces][WLD[result]] += 1
                # record piece WLD stats
                diffs = {p: pieces.count(p.upper()) - pieces.count(p.lower()) for p in set(p.lower() for p in pieces)}
                for p, v in diffs.items():
                    if v < 0 and result in ('1-0', '0-1'):
                        pov_result = '1-0' if result == '0-1' else '0-1'
                    else:
                        pov_result = result
                    piece_score[p][WLD[pov_result]] += abs(v) / (1 + sum(abs(d) for d in diffs.values()) ** 10)
    # Determine order of pieces
    def piece_order(piece):
        return piece_score[piece.lower()][1] / max(sum(piece_score[piece.lower()]), 1) - piece[-1].isupper()
    print('Pieces sorted by strength')
    print(' > '.join(sorted(piece_score, key=piece_order)).upper())
    # Report sorted by various criteria
    sorters = {
        'material': lambda ec: len(ec[0]),
        'frequency': lambda ec: ec[1],
        'entropy': lambda ec: get_entropy(results[ec[0]]),
        'relevance': lambda ec: get_entropy(results[ec[0]]) * ec[1],
    }
    for name, sorter in sorters.items():
        if order_by in ('all', name):
            print('\nEndgames sorted by {}'.format(name))
            print('Pieces\tFreq.\tWin\tLoss\tDraw')
            for endgame, count in sorted(endgames.items(), key=sorter, reverse=True):
                if (    count / total >= min_frequency
                        and get_entropy(results[endgame]) >= min_entropy
                        and get_entropy(results[endgame]) * count / total >= min_relevance):
                    score = ['{:.2%}'.format(i / max(sum(results[endgame]), 1)) for i in results[endgame]]
                    sorted_endgame = ''.join(sorted(endgame, key=piece_order))
                    print('\t'.join((sorted_endgame, '{:.2%}'.format(count / total), *score)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-v', '--variant', help='only required if not annotated in input FEN/EPD')
    parser.add_argument('-m', '--max-pieces', type=int, default=4, help='maximum number of pieces in endgame')
    parser.add_argument('-s', '--stable-ply', type=int, default=1, help='minimum ply since last material change')
    parser.add_argument('-c', '--keep-color', action='store_true', help='report color-specific statistics')
    parser.add_argument('-p', '--ignore-promotion', action='store_true', help='ignore promoted state of pieces')
    parser.add_argument('-e', '--min-entropy', type=float, default=-1, help='filter trivial endgames based on entropy')
    parser.add_argument('-f', '--min-frequency', type=float, default=0, help='filter based on frequency')
    parser.add_argument('-r', '--min-relevance', type=float, default=-1, help='filter based on relevance')
    parser.add_argument('-o', '--order-by', type=str, choices=('material', 'frequency', 'entropy', 'relevance', 'all'),
                        default='relevance', help='sort by %(choices)s (default: %(default)s)')
    args = parser.parse_args()

    with fileinput.input(args.epd_files) as instream:
        evaluate_endgames(instream, args.variant, args.max_pieces, args.stable_ply, args.keep_color,
                          args.min_entropy, args.min_frequency, args.min_relevance, args.order_by, args.ignore_promotion)
