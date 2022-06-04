import argparse
import fileinput
from functools import partial
import re

from tqdm import tqdm
import pandas
from sklearn.linear_model import LogisticRegression



def line_count(filename):
    f = open(filename, 'rb')
    bufgen = iter(partial(f.raw.read, 1024*1024), b'')
    return sum(buf.count(b'\n') for buf in bufgen)


SCORE = {'1-0': 1, '0-1': 0, '1/2-1/2': 0.5}


def piece_values(instream, variant, stable_ply):
    # Before the first line has been read, filename() returns None.
    if instream.filename() is None:
        filename = instream._files[0]
    else:
        filename = instream.filename()
    # When reading from sys.stdin, filename() is "-"
    total = None if (filename == "-") else line_count(filename)

    # collect data
    diffs = []
    results = []
    for epd in tqdm(instream, total=total):
        tokens = epd.strip().split(';')
        fen = tokens[0]
        annotations = dict(token.split(' ', 1) for token in tokens[1:])
        current_variant = annotations.get('variant', variant)
        if not current_variant:
            raise Exception('Variant neither provided in EPD nor as argument')
        board = fen.split(' ')[0]
        pieces = re.findall(r'(?:\+)?[A-Za-z]', board)
        result = annotations.get('result')
        if result in ('1-0', '0-1') and int(annotations.get('hmvc', 0)) >= stable_ply:
            diffs.append({p: pieces.count(p.upper()) - pieces.count(p.lower()) for p in set(p.lower() for p in pieces)})
            results.append(SCORE[result])

    # convert to dataframe
    piece_diffs = pandas.DataFrame(diffs)
    piece_diffs.fillna(0, inplace=True)

    # fit
    model = LogisticRegression(solver='liblinear', C=10.0, random_state=0)
    model.fit(piece_diffs, results)

    # print fitted piece values
    norm = min(v for v in model.coef_[0] if v > 0)
    for p, v in sorted(zip(piece_diffs.columns, model.coef_[0]), key=lambda x: x[1], reverse=True):
        print(p, '{:.2f}'.format(v / norm))
    print("white", model.intercept_[0] / norm)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-v', '--variant', help='only required if not annotated in input FEN/EPD')
    parser.add_argument('-s', '--stable-ply', type=int, default=1, help='minimum ply since last material change')
    args = parser.parse_args()

    with fileinput.input(args.epd_files) as instream:
        piece_values(instream, args.variant, args.stable_ply)
