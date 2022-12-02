# Chess variant stats

This project generates statistics for chess variants using [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) and its python binding pyffish.

## Process
Generating statistics consists of the following steps:
1. `generate_games.py` to generate a set of positions in FEN/EPD format from playing engine games. Alternatively positions can be extracted from other sources such from PGNs with `pgn2epd.py`.
2. `game_stats.py` to report basic game statistics, such as result distribution, game length, and branching factor.
3. `piece_values.py` to fit piece values on the generated data using logistic regression.
4. `evaluate_endgame.py` to identify endgames occuring in the generated positions and collect their result statistics, including insufficient and sufficient mating material.

Steps 2 to 4 are independent of each other, but they can be run on the same input data to save resources on generation.

## Setup
The scripts require at least python3.2 as well as the dependencies from the `requirements.txt`. Install them using
```
pip3 install -r requirements.txt
```

## Usage
A simple example of running the scripts is:
```
python3 generate_games.py --engine fairy-stockfish.exe --variant chess --book chess.epd --movetime 10 --count 1000 > test.epd
python3 game_stats.py --branching-factor test.epd
python3 piece_values.py test.epd
python3 evaluate_endgames.py --max-pieces=4 test.epd
```
Run the scripts with `--help` to get help on the supported parameters.

For reliable results you usually need to generate at least 100k positions, or more depending on the number of pieces, imbalances, and game phases. As starting positions for the data generation (`--book`) you can either use [pregenerated opening books](https://github.com/ianfab/books) or use the [book generator](https://github.com/ianfab/bookgen) yourself.
