# AE2 controller P2P optimiser

Finds a layout of ME Controllers and ME cables for Applied Energistics 2 that
puts as many **ME P2P tunnels** as possible on controller faces, with every
tunnel supplied by a channel.

The problem is solved as a mixed-integer linear program (MILP) in
`controller_milp.py`. There is also a large neighborhood search (LNS) method
which optimizes existing solutions.

We generally assume that smart cables hold 8 channels, and dense cables hold
32 channels. You can create better designs if channel capacity is higher, as
it becomes easier to fit P2Ps.


## Install

Python 3 and three packages:

```
pip install pulp highspy networkx
```

The script works with PuLP 3.x and PuLP 4.x. HiGHS (`highspy`) is the default
solver. `networkx` is used by the independent checker.

## Usage

Solve the problem with a 10-minute limit:

```
python controller_milp.py
```

Longer run on 8 threads:

```
python controller_milp.py --time-limit 86400 --threads 8 --out my_run.json
```

Solve, then run 100 LNS improvement rounds:

```
python controller_milp.py --time-limit 900 --lns 100
```

Improve a saved solution using LNS:

```
python controller_milp.py --init solution_9x9x9.json --lns 200 --out improved.json
```

Run the full solve for two hours, starting from a saved solution (warm start). The
solver begins with that build as its best known solution, so it can discard
worse parts of the search early:

```
python controller_milp.py --warm solution.json --time-limit 7200 --out longer.json
```

Try another root controller, or a smaller volume:

```
python controller_milp.py --root 1 1 1
python controller_milp.py --n 7
```

Require symmetry in all three axes:

```
python controller_milp.py --symmetry xyz
```

### Options

| Option | Default | Meaning |
|---|---|---|
| `--n` | 9 | Side length of the build volume, or 2 + the size of the controller |
| `--symmetry` | `xy` | `xy` (mirror x and y), `xyz` (mirror all three axes) or `none` |
| `--root x y z` | centre | Tile forced to be a controller |
| `--time-limit` | 600 | Seconds for the full solve |
| `--threads` | solver default | CPU threads |
| `--solver` | `highs` | `highs` or `cbc` |
| `--out` | `solution.json` | Where the result is saved |
| `--quiet` | off | Hide the solver log |
| `--lns ITERS` | 0 | LNS improvement rounds after the solve |
| `--init FILE` | none | Start the improvement rounds from a saved solution |
| `--warm FILE` | none | Start the full solve from a saved solution (not with `--init`) |
| `--window` | `2 3` | Box sizes (inside the quarter or octant) freed in each improvement round |
| `--sub-time` | 20 | Seconds per improvement round |
| `--seed` | 0 | Random seed for the improvement rounds |
| `--enable-internal-p2ps` | off | Let cables output into a controller face (unlimited capacity); that face then holds no tunnel |

The defaults for `N`, `ROOT`, the channel capacities and the time limit are
constants at the top of the script.

`--solver cbc` under PuLP 4 needs the `cbc` program installed separately.

## Output

The program prints:

- **status**: `optimal among xy-symmetric builds` (or `xyz-symmetric`, or `unrestricted` for `--symmetry none`), or `feasible (limit
  reached, not proven optimal)`.
- **best bound and gap**: the solver's upper bound on the tunnel count, and
  its distance from the solution found.
- **verified result**: the tunnel count recomputed on the full grid by a
  separate checker that follows each cable's output direction, plus any rule
  violations it finds.
- **the build**, one z-layer at a time. Rows are y, columns are x. The left
  block shows tile types and the right block shows cable output directions:

  | Symbol | Meaning |
  |---|---|
  | `>` `<` | outputs towards +x / −x |
  | `v` `^` | outputs towards +y / −y |
  | `+` `-` | outputs towards +z (next layer) / −z (previous layer) |
  | `C` | controller |
  | `.` | cable that carries no channels |
  | `#` | shell tile |

  With `--enable-internal-p2ps`, an arrow may point at a `C`: that controller
  face is the cable's sink.

The JSON file holds the same build:

- `layout`: tile letter for every `"x,y,z"`.
- `directions`: output direction (`+x`, `-y`, …) for every inner cable that
  carries channels.
- `online_p2p_tunnels` and `accessible_channels`.
- `internal_p2ps`: whether controller faces could be used as sinks.

A P2P tunnel goes on every face where an `N` tile touches a `C` tile, except a
face the cable outputs into (only possible with `--enable-internal-p2ps`). If a
cable touches more controllers than it has channels for, some of its tunnels
stay offline; the program reports only the number that are online.

## Results

See `solutions/README.md`.

## Notes for running the solver

- Set a time limit instead of stopping with Ctrl+C. The full solve only saves
  its result when it finishes.
- LNS rounds save every time they find a better build, so stopping
  them early is safe.
- HiGHS cannot save a search and resume it later. A crash loses the run.
- One of the worse choices I made was having a fixed root for checking connectivity of ME controllers.
  In practice, what this means is that the solver assumes that a certain block
  is always a controller block. By default, this is the center block, and can be changed
  with --root.
- I found RAM to be a more significant limitation than computation time. The
  MILP solver can use huge amounts of RAM.
