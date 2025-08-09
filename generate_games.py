import argparse
import os
import random
import re
import sys
from uuid import uuid4

import pyffish as sf
from tqdm import tqdm

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
        if not sf.legal_moves(variant, start_fen, move_stack):
            pov_score = sf.game_result(variant, start_fen, move_stack)
        else:
            _, pov_score = sf.is_optional_game_end(variant, start_fen, move_stack)
        color = sf.get_fen(variant, start_fen, move_stack).split(' ')[1]
        white_score = pov_score if color == 'w' else -pov_score
        result = '1-0' if white_score > 0 else '0-1' if white_score < 0 else '1/2-1/2'
        game_uuid = uuid4()
        for fen, move, halfmove in zip(fens, move_stack[1:] + ['none'], hmvc):
            yield '{};variant {};bm {};hmvc {};result {};game {}'.format(fen, variant, move, halfmove, result, game_uuid)


def write_fens(stream, engine, variant, count, book, **limits):
    generator = generate_fens(engine, variant, book, **limits)
    for _ in tqdm(range(count)):
        epd = next(generator)
        stream.write(epd + '\n')


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
    parser.add_argument('-ef','--epdfile', type=str, default=None, help='Write generated games to EPD file.')
    parser.add_argument('-ow','--overwrite', action='store_true', help='Overwrite the EPD file instead of appending.')
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
    
    if args.epdfile:
        mode = 'w' if args.overwrite else 'a'
        outstream = open(args.epdfile, mode, encoding='utf-8')
    else:
        outstream = sys.stdout
    
    try:
        write_fens(outstream, engine, args.variant, args.count, args.book, **limits)
    finally:
        if args.epdfile:
            outstream.close()
