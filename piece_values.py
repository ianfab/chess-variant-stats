import argparse
import fileinput
from math import log
import re

import numpy as np
import pandas
from sklearn.linear_model import LogisticRegression
from sklearn.utils import resample
from tqdm import tqdm

from common import sum_line_count, parse_epd


SCORE = {'1-0': 1, '0-1': 0, '1/2-1/2': 0.5}


def estimate_uncertainty_bootstrap(piece_diffs, results, n_bootstrap=100, random_state=42):
    """
    Estimate uncertainty of logistic regression coefficients using bootstrap method.
    
    Args:
        piece_diffs: DataFrame with piece difference features
        results: List of game results (0, 0.5, 1)
        n_bootstrap: Number of bootstrap samples
        random_state: Random seed for reproducibility
    
    Returns:
        (coefficients_mean, coefficients_std, intercept_mean, intercept_std)
    """
    if len(piece_diffs) < 10:  # Too few samples for meaningful uncertainty
        return None, None, None, None
    
    np.random.seed(random_state)
    
    bootstrap_coefs = []
    bootstrap_intercepts = []
    
    for _ in range(n_bootstrap):
        # Bootstrap sample with replacement
        X_boot, y_boot = resample(piece_diffs, results, random_state=np.random.randint(0, 10000))
        
        # Fit model on bootstrap sample
        try:
            model_boot = LogisticRegression(solver='liblinear', C=10.0, random_state=0)
            model_boot.fit(X_boot, y_boot)
            bootstrap_coefs.append(model_boot.coef_[0])
            bootstrap_intercepts.append(model_boot.intercept_[0])
        except:
            # Skip if fitting fails
            continue
    
    if len(bootstrap_coefs) == 0:
        return None, None, None, None
    
    # Calculate statistics across bootstrap samples
    bootstrap_coefs = np.array(bootstrap_coefs)
    bootstrap_intercepts = np.array(bootstrap_intercepts)
    
    coef_mean = np.mean(bootstrap_coefs, axis=0)
    coef_std = np.std(bootstrap_coefs, axis=0)
    intercept_mean = np.mean(bootstrap_intercepts)
    intercept_std = np.std(bootstrap_intercepts)
    
    return coef_mean, coef_std, intercept_mean, intercept_std


def has_imbalance(pieces, imbalance):
    return all(pieces.count(p) - pieces.count(p.swapcase()) >= imbalance.count(p) - imbalance.count(p.swapcase()) for p in set(imbalance))


def game_phase(phases, max_pieces, num_board_pieces):
    return phases - 1 - min(max(int(phases * (num_board_pieces - 1) / max_pieces), 0), phases - 1)


def piece_values(instream, stable_ply, keep_color, unpromoted, normalization, rescale, phases, max_pieces,
                 imbalance, equal_weighted, min_fullmove, n_bootstrap):
    total = sum_line_count(instream)

    # collect data
    diffs = [[] for _ in range(phases)]
    results = [[] for _ in range(phases)]
    last_game = None
    last_set = None
    for epd in tqdm(instream, total=total):
        fen, annotations = parse_epd(epd)
        board = fen.split(' ')[0]
        hm = int(annotations.get('hmvc') or fen.split(' ')[-2])
        fm = int(annotations.get('fmvn') or fen.split(' ')[-1])
        pieces = re.findall(r'[A-Za-z]' if unpromoted else r'(?:\+)?[A-Za-z]', board)
        num_board_pieces = len(re.findall(r'[A-Za-z]', board.split('[')[0]))
        if imbalance:
            for baseImbalance in imbalance:
                for colorImbalance in (baseImbalance, baseImbalance.swapcase()):
                    if has_imbalance(pieces, colorImbalance):
                        pieces.append(colorImbalance)
        result = annotations.get('result')
        if result in ('1-0', '0-1') and hm >= stable_ply and fm >= min_fullmove:
            black_pov = fen.split(' ')[1] == 'b' and not keep_color
            pov_result = ('1-0' if result == '0-1' else '0-1') if black_pov else result
            phase = game_phase(phases, max_pieces, num_board_pieces)
            piece_set = set(min(p, p.swapcase()) for p in pieces)
            if not equal_weighted or (annotations.get('game_uuid') != last_game or piece_set != last_set):
                last_game = annotations.get('game_uuid')
                last_set = piece_set
                diffs[phase].append({p: (pieces.count(p) - pieces.count(p.swapcase())) * (-1 if black_pov else 1) for p in piece_set})
                results[phase].append(SCORE[pov_result])

    for i in range(phases):
        print('\nPhase {} of {}'.format(i + 1, phases))

        if len(diffs[i]) == 0:
            print("No data for this phase")
            continue

        # convert to dataframe
        piece_diffs = pandas.DataFrame(diffs[i])
        piece_diffs.fillna(0, inplace=True)

        if piece_diffs.shape[1] == 0:
            print("No piece differences found")
            continue

        # fit
        model = LogisticRegression(solver='liblinear', C=10.0, random_state=0)
        model.fit(piece_diffs, results[i])

        # estimate uncertainty using bootstrap
        coef_mean, coef_std, intercept_mean, intercept_std = estimate_uncertainty_bootstrap(
            piece_diffs, results[i], n_bootstrap=n_bootstrap)

        # print fitted piece values
        if normalization == 'auto':
            norm = min(abs(v) for p, v in zip(piece_diffs.columns, model.coef_[0]) if len(p) == 1 and v > 0.05) / rescale
        elif normalization == 'natural':
            norm = log(10) / 2
        elif normalization == 'elo':
            norm = log(10) / 400
        else:
            norm = 1
        
        # Print header
        if coef_std is not None:
            print(f"{'Piece':<8} {'Value':<8} {'StdErr':<8}")
            print("-" * 24)
        else:
            print(f"{'Piece':<8} {'Value':<8}")
            print("-" * 16)
            
        for j, (p, v) in enumerate(sorted(zip(piece_diffs.columns, model.coef_[0]), key=lambda x: x[1], reverse=True)):
            if coef_std is not None:
                std_err = coef_std[list(piece_diffs.columns).index(p)] / norm
                print(f"{p:<8} {v / norm:>7.2f} {std_err:>7.2f}")
            else:
                print(f"{p:<8} {v / norm:>7.2f}")
        
        # Print intercept
        move_label = 'white' if keep_color else 'move'
        if intercept_std is not None:
            intercept_std_norm = intercept_std / norm
            print(f"{move_label:<8} {model.intercept_[0] / norm:>7.2f} {intercept_std_norm:>7.2f}")
        else:
            print(f"{move_label:<8} {model.intercept_[0] / norm:>7.2f}")
            
        # Print uncertainty information
        if coef_std is not None:
            print(f"\nUncertainty estimated using bootstrap method with {len(piece_diffs)} samples")
        else:
            print(f"\nInsufficient data ({len(piece_diffs)} samples) for uncertainty estimation")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('epd_files', nargs='*')
    parser.add_argument('-s', '--stable-ply', type=int, default=1, help='minimum ply since last material change')
    parser.add_argument('-c', '--keep-color', action='store_true', help='report color-specific statistics')
    parser.add_argument('-u', '--unpromoted', action='store_true', help='ignore promoted state of pieces')
    parser.add_argument('-i', '--imbalance', action='append', help='imbalance to evaluate. Can be specified more than once.')
    parser.add_argument('-n', '--normalization', choices=['off', 'elo', 'natural', 'auto'], default='auto', help='define normalization scale, one of %(choices)s')
    parser.add_argument('-r', '--rescale', type=float, default=1, help='rescale. only for "auto" normalization')
    parser.add_argument('-p', '--phases', type=int, default=1, help='number of game phases')
    parser.add_argument('-m', '--max-pieces', type=int, default=32, help='maximum possible number of pieces, for game phases')
    parser.add_argument('-e', '--equal-weighted', action='store_true', help='use each material configuration only once per game')
    parser.add_argument('-f', '--min-fullmove', type=int, default=0, help='minimum fullmove count to consider position')
    parser.add_argument('--bootstrap-samples', type=int, default=100, help='number of bootstrap samples for uncertainty estimation')
    args = parser.parse_args()
    if args.rescale != 1 and args.normalization != 'auto':
        parser.error('Rescaling only supported for "auto" normalization.')

    with fileinput.input(args.epd_files) as instream:
        piece_values(instream, args.stable_ply, args.keep_color, args.unpromoted,
                     args.normalization, args.rescale, args.phases, args.max_pieces,
                     args.imbalance, args.equal_weighted, args.min_fullmove, args.bootstrap_samples)
