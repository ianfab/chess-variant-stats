import argparse
import os
import random
import re
import sys

from tqdm import tqdm
import pyffish as sf

import uci


def get_pieces(fen):
    return tuple(sorted(re.findall(r'(?:\+)?[A-Za-z]', fen.split(' ')[0])))


def generate_fens(engine, variant, book, **limits):
    if variant not in sf.variants():
        raise Exception("Unsupported variant: {}".format(variant))

    startfens = list()
    if book:
        with open(book) as epdfile:
            for l in epdfile:
                startfens.append(l.strip())
    else:
        startfens.append(sf.start_fen(variant))

    engine.setoption('UCI_Variant', variant)

    while True:
        engine.newgame()
        move_stack = []
        start_fen = random.choice(startfens)
        fens = list()
        hmvc = list()
        last_change = 0
        while (sf.legal_moves(variant, start_fen, move_stack)
               and not sf.is_optional_game_end(variant, start_fen, move_stack)[0]):
            engine.position(start_fen, move_stack)
            bestmove, _ = engine.go(**limits)
            move_stack.append(bestmove)
            fens.append(sf.get_fen(variant, start_fen, move_stack))
            if len(fens) >= 2 and get_pieces(fens[-2]) != get_pieces(fens[-1]):
                last_change = len(move_stack)
            hmvc.append(len(move_stack) - last_change)
        pov_score = sf.game_result(variant, start_fen, move_stack)
        color = sf.get_fen(variant, start_fen, move_stack).split(' ')[1]
        white_score = pov_score if color == 'w' else -pov_score
        result = '1-0' if white_score > 0 else '0-1' if white_score < 0 else '1/2-1/2'
        for fen, halfmove in zip(fens, hmvc):
            yield '{};result {};hmvc {}'.format(fen, result, halfmove)


def write_fens(stream, engine, variant, count, book, **limits):
    generator = generate_fens(engine, variant, book, **limits)
    for _ in tqdm(range(count)):
        fen = next(generator)
        stream.write('{};variant {}'.format(fen, variant) + os.linesep)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--engine', required=True, help='chess variant engine path, e.g., to Fairy-Stockfish')
    parser.add_argument('-o', '--ucioptions', type=lambda kv: kv.split("="), action='append', default=[],
                        help='UCI option as key=value pair. Repeat to add more options.')
    parser.add_argument('-v', '--variant', default='chess', help='variant to generate positions for')
    parser.add_argument('-c', '--count', type=int, default=1000, help='number of positions')
    parser.add_argument('-d', '--depth', type=int, default=None, help='search depth')
    parser.add_argument('-t', '--movetime', type=int, default=None, help='search movetime (ms)')
    parser.add_argument('-b', '--book', type=str, default=None, help='EPD opening book')
    args = parser.parse_args()

    engine = uci.Engine([args.engine], dict(args.ucioptions))
    sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
    limits = dict()
    if args.depth:
        limits['depth'] = args.depth
    if args.movetime:
        limits['movetime'] = args.movetime
    if not limits:
        parser.error('At least one of --depth and --movetime is required.')
    write_fens(sys.stdout, engine, args.variant, args.count, args.book, **limits)
