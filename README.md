# AE2 controller P2P optimiser

Finds a layout of ME Controllers and ME cables for Applied Energistics 2 that
puts as many **ME P2P tunnels** as possible on controller faces, with every
tunnel supplied by a channel. Each online tunnel makes 32 controller channels
accessible, so more tunnels means more channels.

The problem is solved as a mixed-integer linear program (MILP) in
`controller_milp.py`.

## The problem

The build volume is an N×N×N cube (default 9×9×9). Every tile is one of:

| Letter | Block | Rules |
|---|---|---|
| `C` | ME Controller | Only in the inner (N−2)³ block (7×7×7 for N = 9). |
| `N` | ME cable (glass, covered or smart) | Carries 8 channels. Can hold P2P tunnels. |
| `D` | ME dense cable | Carries 32 channels. Cannot hold P2P tunnels. |

**Controller rules**

- All controllers must form one connected structure.
- No controller may have controller neighbours on both sides along two
  different axes. So a controller never has 5 or 6 controller neighbours, and
  never 4 that lie in one plane.

**P2P tunnels**

- An ME cable can hold one P2P tunnel on each face that touches a controller.
- A tunnel is *online* if it gets a channel. That channel must be routed
  through cable tiles to the outer shell of the volume.
- A cable passes at most 8 channels and a dense cable at most 32. A cable's
  own tunnels count towards its 8.
- Every inner cable sends all the channels it carries to **exactly one**
  neighbour (another cable or a shell tile).
- Outer-shell tiles have unlimited capacity. The model fixes them as ME cable.
- Tunnels without a channel are allowed. They just don't count.
- With `--enable-internal-p2ps`, an inner cable (normal or dense) may also
  output into a neighbouring controller face. That face takes any number of
  channels, but it then cannot hold a P2P tunnel, so it doesn't count towards
  the goal. Without the option, cables never output into controllers.

**Goal:** maximise the number of online P2P tunnels.

## Restrictions the model adds

These are choices made to keep the model small. They can cost some tunnels.

- **Symmetric builds only.** `--symmetry` chooses which mirror symmetry the
  build must have:
  - `xy` (default): mirror-symmetric through the x and y centre planes
    (x → N−1−x and y → N−1−y), free in z. The model has variables for one
    quarter: x and y up to the middle, all z (112 tiles instead of 343 for
    N = 9).
  - `xyz`: mirror-symmetric through all three centre planes. The model has
    variables for one octant (64 tiles for N = 9). Smaller and much faster
    to solve, but it can miss better builds that are only xy-symmetric.
- **Symmetric routing only.** The cable output directions must have the same
  symmetry. One consequence: a cable lying on a mirrored centre plane cannot
  output across that plane. With `xy`, a cable on the vertical centre line
  can only output along z; with `xyz`, the centre tile carries nothing.
- **A fixed root controller.** One chosen tile (default: the centre) is forced
  to be a controller. Its mirror images become controllers as well.

"Optimal" in the program's output always means optimal among builds and
routings that satisfy these restrictions.

## Install

Python 3 and three packages:

```
pip install pulp highspy networkx
```

The script works with PuLP 3.x and PuLP 4.x. HiGHS (`highspy`) is the default
solver. `networkx` is used by the independent checker.

## Usage

Solve the 9×9×9 problem with a 10-minute limit:

```
python controller_milp.py
```

Longer run on 8 threads:

```
python controller_milp.py --time-limit 86400 --threads 8 --out my_run.json
```

Solve, then run 100 improvement rounds:

```
python controller_milp.py --time-limit 900 --lns 100
```

Keep improving a saved solution (skips the full solve):

```
python controller_milp.py --init solution_9x9x9.json --lns 200 --out improved.json
```

Try another root controller, or a smaller volume:

```
python controller_milp.py --root 1 1 1
python controller_milp.py --n 7
```

Require symmetry in all three axes (smaller, faster model):

```
python controller_milp.py --symmetry xyz
```

### Options

| Option | Default | Meaning |
|---|---|---|
| `--n` | 9 | Side length of the build volume |
| `--symmetry` | `xy` | `xy` (mirror x and y) or `xyz` (mirror all three axes) |
| `--root x y z` | centre | Tile forced to be a controller |
| `--time-limit` | 600 | Seconds for the full solve |
| `--threads` | solver default | CPU threads |
| `--solver` | `highs` | `highs` or `cbc` |
| `--out` | `solution.json` | Where the result is saved |
| `--quiet` | off | Hide the solver log |
| `--lns ITERS` | 0 | Improvement rounds after the solve |
| `--init FILE` | none | Start the improvement rounds from a saved solution |
| `--window` | `2 3` | Box sizes (inside the quarter or octant) freed in each improvement round |
| `--sub-time` | 20 | Seconds per improvement round |
| `--seed` | 0 | Random seed for the improvement rounds |
| `--enable-internal-p2ps` | off | Let cables output into a controller face (unlimited capacity); that face then holds no tunnel |

The defaults for `N`, `ROOT`, the channel capacities and the time limit are
constants at the top of the script.

`--solver cbc` under PuLP 4 needs the `cbc` program installed separately.

## Output

The program prints:

- **status**: `optimal among xy-symmetric builds` (or `xyz-symmetric`), or `feasible (limit
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

Best I've currently found is

| Volume | Online P2P tunnels | Channels | Status |
|---|---|---|---|
| 9×9×9 | 752 | 24,064 | Best found; proven upper bound about 790 |

This was found with symmetry in all three axes (now `--symmetry xyz`).

"Proven optimal" is within the restrictions listed above.

## Notes for long runs

- Set a time limit instead of stopping with Ctrl+C. The full solve only saves
  its result when it finishes.
- Improvement rounds save every time they find a better build, so stopping
  them early is safe.
- HiGHS cannot save a search and resume it later. A crash loses the run.
- The choice of root controller can change the optimum. It is worth trying a
  few roots before committing a long run to one.
