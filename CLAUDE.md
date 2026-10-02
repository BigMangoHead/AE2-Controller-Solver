# CLAUDE.md

Notes for an agent working on this project. Read `README.md` for the problem
statement and usage, and the docstring of `controller_milp.py` for the full
model and the proofs behind the symmetry reduction.

## What this is

A MILP that designs an Applied Energistics 2 (Minecraft mod) build: ME
Controllers and ME cables in an N×N×N volume (default 9×9×9), maximising the
number of ME P2P tunnels on controller faces that get a channel. Each online
tunnel gives 32 controller channels.

Everything is in one file, `controller_milp.py` (Python, PuLP + HiGHS, with
networkx for the checker).

## Vocabulary

| Term | Meaning |
|---|---|
| `C`, `N`, `D` | Tile letters: ME Controller, ME cable (8 channels), ME dense cable (32 channels). Used in builds and JSON files. |
| P2P tunnel | Sits on an `N` tile's face that touches a `C` tile. One per such face. |
| online | The tunnel's channel reaches the outer shell through cable tiles. |
| shell | The outermost layer of the volume. Fixed as `N`, unlimited capacity, acts as the sink. |
| inner | The (N−2)³ block inside the shell. Only place controllers may go. |
| quarter | Inner tiles with x ≤ H and y ≤ H, H = (N−1)//2, any z. The only tiles with variables. Builds are mirror-symmetric in x and y only (`MIRROR_AXES`); z is not mirrored. |
| direction / pointer | The one neighbour an inner cable sends all its channels to. |
| root | A tile forced to be a controller; source of the connectivity flow. |
| LNS | Large-neighbourhood search: free a small box of quarter tiles, fix the rest, re-solve. |

Earlier versions of the code called tunnels "connections", ME cable "normal
cable", and online "valid". Old logs and solution files may use those words.
Before the switch to x/y symmetry, the model mirrored all three axes and the
variable region was the "octant" (`"symmetry": "octant"` in old files). Those
builds are also x/y-symmetric, so `--init` accepts them.

## Commands

```
pip install pulp highspy networkx

python controller_milp.py --n 5 --quiet        # under 1 s
python controller_milp.py --n 6 --quiet        # about 1 s
python controller_milp.py --n 7 --quiet        # not proven in 5 min (4 threads)
python controller_milp.py                      # 9x9x9, 10-minute limit
python controller_milp.py --init solution_9x9x9.json --lns 50
```

## Regression values

After any change to the model, these must still come out, all proven optimal,
with "violations: none" and "symmetric: True":

| `--n` | Online P2P tunnels | Model size |
|---|---|---|
| 5 | 74 | 220 variables, 338 constraints |
| 6 | 140 | 348 variables, 534 constraints |
| 7 | not proven: 296 found, bound 327.9 after 5 min on 4 threads | 950 variables, 1552 constraints |

With `--enable-internal-p2ps`:

| `--n` | Online P2P tunnels | Model size |
|---|---|---|
| 5 | 74 | 220 variables, 350 constraints |
| 6 | 140 | 348 variables, 550 constraints |
| 7 | 308 (proven in 241 s on 4 threads) | 950 variables, 1597 constraints |

For quick checks use 5 and 6. Since every octant-symmetric build is also
x/y-symmetric, results must never fall below the old octant values (70, 120,
292; 302 with `--enable-internal-p2ps` on 7).

## How the model is put together

`build_model()` creates, for quarter tiles only:

- `ctrl[t]`, `cable[t]`: binary tile type. Dense cable is `1 - ctrl - cable`.
- `p2p[arc]`: continuous 0..1, a tunnel on cable `u` facing controller `v`.
- `chan[arc]`: continuous, channels passed along an arc.
- `points[arc]`: binary, the cable's output direction is this arc.
- `link[a,b]`: continuous, connectivity flow between controller tiles on the
  quotient graph.

Things that are easy to break:

1. **Canonical arcs.** `p2p`, `chan` and `points` are stored per canonical arc
   `canon_arc(a, b)`: the tail is mapped into the quarter, and the head may
   land outside it. Always go through the helper closures (`tunnel`,
   `channels`, `pointer`) and sum over all 6 full-grid neighbours of a quarter
   tile. Do not index these dicts by raw tile pairs.
2. **Centre-plane tiles.** For odd N, a tile on the x or y centre plane has
   two arcs across that plane that share one variable. The sums count it
   twice on purpose. That is what makes such a cable unable to point across
   its own mirror plane, which symmetric routing requires. The z centre plane
   is not a mirror plane, so nothing like this happens there.
3. **Connectivity needs two conditions.** The quotient graph being connected
   is not enough. The `central_layer_*` constraints (one per mirrored axis,
   so x and y) are also required. The proof is in the docstring.
4. **Pointer cycles need no constraint.** Conservation already forces zero
   tunnels into a cycle.
5. **`internal_p2ps` (`--enable-internal-p2ps`).** Off by default. When on,
   `dir_not_ctrl` is replaced by `sink_or_p2p` (`points + p2p <= 1` on the
   same canonical arc), and conservation is relaxed at controllers through a
   big-M on `ctrl` (`chan_sink_*`). The checker takes the same flag: a cable
   pointing at a controller gets an edge to T and loses one tunnel slot.
6. **The objective counts the full grid.** It loops over all inner tiles, not
   just the quarter, and adds shell-cable tunnels as `k * ctrl`.

`count_online_p2p()` is the independent checker. It works on the full grid,
shares no variables with the MILP, and must stay that way. Every result
reported to the user should come from it, not from the MILP objective.

## PuLP 3 and PuLP 4

The user runs PuLP 4.0.0. The script must work on both 3.x and 4.x:

- Create variables with `prob.add_variable(...)`. `pulp.LpVariable(..., cat=)`
  fails in PuLP 4.
- Never write `var_a == var_b` as a constraint. PuLP 4 evaluates it to a plain
  bool. Write `var_a - var_b == 0`.
- Inside nested functions use `prob.addConstraint(expr, name)`. `prob += ...`
  there makes `prob` a local variable and crashes.
- Use `prob.numConstraints()`, not `len(prob.constraints)`.
- `prob.solve()` returns an int in PuLP 3 and a stats object in PuLP 4. There
  is no `prob.sol_status` or `pulp.LpStatus` in PuLP 4. Use `solve_outcome()`,
  which reads the status and bound straight from the HiGHS model.
- `PULP_CBC_CMD` does not exist in PuLP 4. Use `make_cbc()`.

PuLP 4.0.0 needs Python 3.12 or newer.

## Results so far

Current rules (one output direction per cable, x/y symmetry), centre root:

| Volume | Result | With `--enable-internal-p2ps` |
|---|---|---|
| 5×5×5 | 74, proven | 74, proven |
| 6×6×6 | 140, proven | 140, proven |
| 7×7×7 | 298, not proven (5-min solve: 296, bound 327.9; 4 LNS rounds from the old 292 build: 298) | 308, proven |
| 8×8×8 | not run | not run |
| 9×9×9 | not run | not run |

Earlier results with symmetry in all three axes (octant model), centre root:
5×5×5 70, 6×6×6 120, 7×7×7 292 (302 with `--enable-internal-p2ps`), all
proven. 9×9×9: 736, not proven (a 9-minute solve gave 724 with bound 929.9;
LNS raised it to 736).

On the cost of symmetric routing: for the optimal 7×7×7 build, a full-grid
model with unrestricted directions also gave 292. A full-grid search over both
builds and unrestricted directions on 7×7×7 did not finish (286 found, bound
348), so the cost in general is not known.

## Open questions

- 9×9×9 has not been run with x/y symmetry. Old octant builds (736) are valid
  `--init` starting points.
- The octant 9×9×9 gap (736 found, bound about 930) is mostly a weak LP relaxation.
  Tighter constraints are more likely to help than more solver time.
- Roots other than the centre have not been tried under the current rules.
- No estimate exists for how long a proof of optimality on 9×9×9 would take.
- Whether asymmetric builds or asymmetric routing beat the symmetric optimum.

## Assumptions not checked against the game

The rules came from the user's description. These points were taken as given
and never verified in AE2 itself:

- An online ME P2P tunnel provides 32 channels (`CHANNELS_PER_P2P`). This only
  affects the reported channel total, not the optimisation.
- The player can force each cable to output in the direction the solution
  chooses.
- With `--enable-internal-p2ps`: a controller face accepts any number of
  channels from a cable, and that face then cannot hold a tunnel.
- Shell tiles have unlimited capacity and count as the destination.

If the user reports that a build does not work in game, check these first.

## Working with the user

- The user asked not to be given estimates that are not well founded. If you
  cannot back a number, say so.
- Do not start long solver runs without being asked. Small-grid checks are
  fine.
- The user wants changes to the model explained before they are implemented.
- The user has a machine available for long runs. HiGHS cannot checkpoint, so
  a crashed run is lost.
- When running in a sandbox, long background solves can be killed when a
  waiting command times out. Use time limits and keep waits short. LNS saves
  as it goes; the full solve does not.
