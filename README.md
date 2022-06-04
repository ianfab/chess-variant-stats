# Chess variant stats

This project generates statistics for chess variants using [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) and its python binding pyffish.

## Process
Generating statistics consists of the following steps:
1. `generate_games.py` to generate a set of positions in FEN/EPD format from playing engine games. This step can be skipped if positions are extracted from other sources such as databases of human games.
2. `piece_values.py` to fit piece values on the generated data using logistic regression.
3. `evaluate_endgame.py` to identify endgames occuring in the generated positions and collect their result statistics.

Steps 2 and 3 are independent of each other, but they can be run on the same input data to save resources on generation.

## Setup
The scripts require at least python3.2 as well as the dependencies from the `requirements.txt`. Install them using
```
pip3 install -r requirements.txt
```

## Usage
A simple example of running the scripts is:
```
python3 generate_games.py --engine fairy-stockfish.exe --variant chess --book chess.epd --movetime 10 --count 1000 > test.epd
python3 piece_values.py test.epd
python3 evaluate_endgames.py test.epd --max-pieces 4
```
Run the scripts with `-h` to get help on the supported parameters.
