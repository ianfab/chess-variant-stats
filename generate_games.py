import argparse
import multiprocessing
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




# Globals initialised in worker processes for streaming generation
_WORKER_ENGINE = None
_WORKER_GENERATOR = None


def _init_worker(engine_path, uci_options, variant, book, limits):
    """Pool initializer to create a persistent engine & generator per worker."""
    import atexit
    import time
    global _WORKER_ENGINE, _WORKER_GENERATOR

    # Create engine per process and configure
    _WORKER_ENGINE = uci.Engine([engine_path], dict(uci_options) if uci_options else {})
    sf.set_option("VariantPath", _WORKER_ENGINE.options.get("VariantPath", ""))

    # Unique seed per process
    random.seed(hash((os.getpid(), time.time())))

    # Create a generator that we can pull from for each task
    _WORKER_GENERATOR = generate_fens(_WORKER_ENGINE, variant, book, **limits)

    # Ensure engine is terminated when the worker exits
    def _cleanup():
        try:
            if _WORKER_ENGINE and hasattr(_WORKER_ENGINE, 'process') and _WORKER_ENGINE.process:
                try:
                    _WORKER_ENGINE.process.terminate()
                    _WORKER_ENGINE.process.wait(timeout=5)
                except Exception:
                    try:
                        _WORKER_ENGINE.process.kill()
                    except Exception:
                        pass
        except Exception:
            pass

    atexit.register(_cleanup)


def _generate_one(_):
    """Return one generated EPD string using the process-local generator.

    Returns None on failure to allow the main process to continue and update progress.
    """
    try:
        return next(_WORKER_GENERATOR)
    except StopIteration:
        # Should not normally happen; signal failure and continue
        return None
    except Exception as e:
        print(f"Warning: Worker {os.getpid()} failed to generate position: {e}", file=sys.stderr)
        return None


def worker_generate_fens(args):
    """Worker function for multiprocessing that generates a portion of FENs."""
    engine_path, uci_options, variant, book, limits, count, worker_id = args
    
    engine = None
    try:
        # Create a new engine instance for this worker
        engine = uci.Engine([engine_path], dict(uci_options) if uci_options else {})
        sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
        
        # Set up random seed for this worker to ensure different games
        # Combine worker_id with current time and process id for better randomness
        import time
        random.seed(hash((worker_id, time.time(), os.getpid())))
        
        results = []
        generator = generate_fens(engine, variant, book, **limits)
        
        for _ in range(count):
            try:
                epd = next(generator)
                results.append(epd)
            except StopIteration:
                # Generator exhausted, this shouldn't normally happen but is handled
                break
            except Exception as e:
                # Log the error but continue with other positions
                print(f"Warning: Worker {worker_id} failed to generate position: {e}", file=sys.stderr)
                continue
        
        return results
        
    except Exception as e:
        # Handle engine creation or other critical errors
        error_msg = f"Worker {worker_id} failed: {e}"
        print(error_msg, file=sys.stderr)
        raise RuntimeError(error_msg)
    finally:
        # Clean up engine process if it was created
        if engine and hasattr(engine, 'process') and engine.process:
            try:
                engine.process.terminate()
                engine.process.wait(timeout=5)  # Wait up to 5 seconds
            except Exception:
                # Force kill if terminate doesn't work
                try:
                    engine.process.kill()
                except Exception:
                    pass  # Process might already be dead


def write_fens(stream, engine_path, uci_options, variant, count, book, workers, **limits):
    """Write FENs streaming to the output and updating progress per item.

    For workers > 1, uses a Pool with a process-local persistent engine and generator
    to avoid re-initialization overhead and to allow frequent tqdm updates.
    """
    # Single-worker fast path: no multiprocessing overhead, update per item
    if workers <= 1:
        engine = None
        try:
            engine = uci.Engine([engine_path], dict(uci_options) if uci_options else {})
            sf.set_option("VariantPath", engine.options.get("VariantPath", ""))
            gen = generate_fens(engine, variant, book, **limits)
            failures = 0
            with tqdm(total=count, desc="Generating positions") as pbar:
                for _ in range(count):
                    epd = None
                    try:
                        epd = next(gen)
                    except Exception as e:
                        failures += 1
                        print(f"Warning: generation failed: {e}", file=sys.stderr)
                    if epd:
                        stream.write(epd + '\n')
                    pbar.update(1)
            if failures:
                print(f"Warning: {failures} positions failed to generate.", file=sys.stderr)
        finally:
            if engine and hasattr(engine, 'process') and engine.process:
                try:
                    engine.process.terminate()
                    engine.process.wait(timeout=5)
                except Exception:
                    try:
                        engine.process.kill()
                    except Exception:
                        pass
        return

    # Multiprocessing path: per-item tasks from persistent per-process generators
    failures = 0
    written = 0
    try:
        with multiprocessing.Pool(
            processes=workers,
            initializer=_init_worker,
            initargs=(engine_path, uci_options, variant, book, limits),
        ) as pool:
            with tqdm(total=count, desc="Generating positions") as pbar:
                for epd in pool.imap_unordered(_generate_one, range(count), chunksize=1):
                    if epd:
                        stream.write(epd + '\n')
                        written += 1
                    else:
                        failures += 1
                    pbar.update(1)
    except Exception as e:
        print(f"Error during parallel generation: {e}", file=sys.stderr)
        if written:
            print(f"Partial results available: {written} positions generated", file=sys.stderr)
        else:
            raise
    if failures:
        print(f"Warning: {failures} positions failed to generate. Wrote {written} out of {count} requested positions.", file=sys.stderr)


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
    parser.add_argument('-w', '--workers', type=int, default=1, help='Number of parallel workers (default: 1)')
    args = parser.parse_args()
    
    if args.workers < 1:
        parser.error('Number of workers must be at least 1.')
    
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
        # Always use the unified multi-threading compatible approach
        write_fens(outstream, args.engine, args.ucioptions, args.variant, 
                   args.count, args.book, args.workers, **limits)
    finally:
        if args.epdfile:
            outstream.close()
