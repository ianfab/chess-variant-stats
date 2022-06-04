# Chess variant stats

This project generates statistics for chess variants using [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) and its python binding pyffish.

## Process
Generating endgame statistics consists of the following steps:
1. `generate_games.py` to generate a set of positions in FEN/EPD format from playing engine games. This step can be skipped if positions are extracted from other sources such as databases of human games.
2. `evaluate_endgame.py` to identify endgames occuring in the generated positions and collect their result statistics.

## Setup
The scripts require at least python3.2 as well as the dependencies from the `requirements.txt`. Install them using
```
pip3 install -r requirements.txt
```

## Usage
A simple example of running the scripts is:
```
python3 generate_games.py --engine fairy-stockfish.exe --variant chess --book chess.epd --movetime 10 --count 1000 > test.epd
python3 evaluate_endgames.py test.epd --max-pieces 4 --stable-ply 1
```
Run the scripts with `-h` to get help on the supported parameters.
