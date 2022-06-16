from functools import partial
import math


def get_files(instream):
    if instream.filename() is None:
        return instream._files
    else:
        return [instream.filename()]


def line_count(filename):
    with open(filename, 'rb') as f:
        bufgen = iter(partial(f.raw.read, 1024*1024), b'')
        return sum(buf.count(b'\n') for buf in bufgen)


def sum_line_count(instream):
    filenames = get_files(instream)
    # When reading from sys.stdin, filename() is "-"
    return None if filenames[0] == "-" else sum(line_count(filename) for filename in filenames)


def parse_epd(epd):
    tokens = epd.strip().split(';')
    fen = tokens[0]
    ops = dict(token.split(' ', 1) for token in tokens[1:])
    return fen, ops


def get_entropy(wld):
    """Calculates information theoretical entropy"""
    norm = sum(wld)
    wld = [i for i in wld if i > 0]
    return -sum(math.log2(p / norm) * p / norm for p in wld)
