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
| symmetry | `--symmetry xy` (default) mirrors x and y; `--symmetry xyz` mirrors all three axes. `SYMMETRIES` maps the name to the mirrored axes, which are threaded through `mirrors`, `rep`, `canon_arc`, `extent`, `region` and `is_symmetric`. |
| region | The only tiles with variables: inner tiles with t_i ≤ H = (N−1)//2 on every mirrored axis. Called the "quarter" for xy (any z) and the "octant" for xyz. |
| direction / pointer | The one neighbour an inner cable sends all its channels to. |
| root | A tile forced to be a controller; source of the connectivity flow. |
| LNS | Large-neighbourhood search: free a small box of region tiles, fix the rest, re-solve. |

Earlier versions of the code called tunnels "connections", ME cable "normal
cable", and online "valid". Old logs and solution files may use those words.
Solution files from before `--symmetry` existed say `"symmetry": "octant"`
(that is xyz). xyz builds are also xy-symmetric, so `--init` accepts them in
both modes; an xy-only build is refused under `--symmetry xyz`.

## Commands

```
pip install pulp highspy networkx

python controller_milp.py --n 5 --quiet        # under 1 s
python controller_milp.py --n 6 --quiet        # about 1 s
python controller_milp.py --n 7 --quiet        # not proven in 5 min (4 threads)
python controller_milp.py --n 7 --quiet --symmetry xyz   # about 5 s
python controller_milp.py                      # 9x9x9, 10-minute limit
python controller_milp.py --init solution_9x9x9.json --lns 50
python controller_milp.py --warm solution_9x9x9.json      # full solve, warm start
```

The user's venv is `../milp` (`../run.sh` wraps it), and their solution files
are in `../solutions/`.

## Regression values

After any change to the model, these must still come out, all proven optimal
unless noted, with "violations: none" and "xy-symmetric: True" /
"xyz-symmetric: True". Check both symmetries.

`--symmetry xyz` (all about 5 s or less):

| `--n` | Online P2P tunnels | Model size | With `--enable-internal-p2ps` |
|---|---|---|---|
| 5 | 70 | 133 variables, 314 constraints | 70; 322 constraints |
| 6 | 120 | 169 variables, 398 constraints | 120; 406 constraints |
| 7 | 292 | 537 variables, 1294 constraints | 302; 1321 constraints |

`--symmetry xy` (default):

| `--n` | Online P2P tunnels | Model size | With `--enable-internal-p2ps` |
|---|---|---|---|
| 5 | 74 | 220 variables, 509 constraints | 74; 521 constraints |
| 6 | 140 | 348 variables, 813 constraints | 140; 829 constraints |
| 7 | not proven (see Results) | 950 variables, 2268 constraints | 308 (proven before the strengthening cuts, 241 s on 4 threads); 2313 constraints |

Without the strengthening cuts (`build_model(..., cuts=frozenset())`) the
constraint counts were: xyz 211/259/890 (219/267/917 with internal P2Ps), xy
338/534/1552 (350/550/1597).

For quick xy checks use 5 and 6, and only compare the 7×7×7 model size.
Every xyz-symmetric build is also xy-symmetric, so an xy result must never
fall below the xyz one.

## How the model is put together

`build_model()` creates, for region tiles only:

- `ctrl[t]`, `cable[t]`: binary tile type. Dense cable is `1 - ctrl - cable`.
- `p2p[arc]`: continuous 0..1, a tunnel on cable `u` facing controller `v`.
- `chan[arc]`: continuous, channels passed along an arc.
- `points[arc]`: binary, the cable's output direction is this arc.
- `link[a,b]`: continuous, connectivity flow between controller tiles on the
  quotient graph.

Things that are easy to break:

1. **Canonical arcs.** `p2p`, `chan` and `points` are stored per canonical arc
   `canon_arc(a, b)`: the tail is mapped into the region, and the head may
   land outside it. Inside `build_model` use the closures `rep_` and `arc`,
   which carry the mirrored axes. Always go through the helper closures
   (`tunnel`, `channels`, `pointer`) and sum over all 6 full-grid neighbours
   of a region tile. Do not index these dicts by raw tile pairs.
2. **Centre-plane tiles.** For odd N, a tile on the centre plane of a
   mirrored axis has two arcs across that plane that share one variable. The
   sums count it twice on purpose. That is what makes such a cable unable to
   point across its own mirror plane, which symmetric routing requires. With
   xy, the z centre plane is not a mirror plane, so this does not happen there.
3. **Connectivity needs two conditions.** The quotient graph being connected
   is not enough. The `central_layer_*` constraints (one per mirrored axis:
   2 for xy, 3 for xyz) are also required. The proof is in the docstring.
4. **Pointer cycles need no constraint.** Conservation already forces zero
   tunnels into a cycle.
5. **`internal_p2ps` (`--enable-internal-p2ps`).** Off by default. When on,
   `dir_not_ctrl` is replaced by `sink_or_p2p` (`points + p2p <= 1` on the
   same canonical arc), and conservation is relaxed at controllers through a
   big-M on `ctrl` (`chan_sink_*`). The checker takes the same flag: a cable
   pointing at a controller gets an edge to T and loses one tunnel slot.
6. **The objective counts the full grid.** It loops over all inner tiles, not
   just the region, and adds shell-cable tunnels as `k * ctrl`.
7. **Strengthening cuts (`CUTS`).** `needs_out`, `chan_cable`, `dir_used` and
   `ctrl_nbr` are not needed for correctness. Each is valid for at least one
   optimal solution, not for every feasible one (`dir_used` in particular
   forbids pointing with zero channels). A new rule must keep at least one
   optimum feasible under them. `build_model(cuts=...)` takes a subset for
   benchmarking. The reasoning and the families that were tried and dropped
   are in the docstring.

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

One output direction per cable, centre root.

`--symmetry xy`:

| Volume | Result | With `--enable-internal-p2ps` |
|---|---|---|
| 5×5×5 | 74, proven | 74, proven |
| 6×6×6 | 140, proven | 140, proven |
| 7×7×7 | 298, not proven (5-min solve: 296, bound 327.9; 4 LNS rounds from the old 292 build: 298) | 308, proven |
| 8×8×8 | not run | not run |
| 9×9×9 | 729 found, bound 966.2 (user's 20-min run) | 768 found, bound 973.9 (user's 20-min run) |

`--symmetry xyz`:

| Volume | Result | With `--enable-internal-p2ps` |
|---|---|---|
| 5×5×5 | 70, proven | 70, proven |
| 6×6×6 | 120, proven | 120, proven |
| 7×7×7 | 292, proven | 302, proven |
| 8×8×8 | not run | not run |
| 9×9×9 | 752, not proven, bound 797.9 (user's 8-hour run, before the strengthening cuts) | 778 found, bound 896.3 (user's 10-min run) |

On the cost of symmetric routing: for the optimal 7×7×7 build, a full-grid
model with unrestricted directions also gave 292. A full-grid search over both
builds and unrestricted directions on 7×7×7 did not finish (286 found, bound
348), so the cost in general is not known.

The user's solution files are in `../solutions/`. Their long xy and
internal-P2P runs were started before the strengthening cuts.

### Benchmarks of the strengthening cuts

Each run used 1 HiGHS thread, alongside 3 of the user's solves on an 8-core
machine. Timings vary by about ±20%.

| Case | Without cuts | With `CUTS` |
|---|---|---|
| xyz 7×7×7, proof time | 15.5 s | 5.2 s |
| xyz 7×7×7 + internal P2Ps, proof time | 3.1 s | 5.6 s (too short to judge) |
| xy 7×7×7, 240 s | 296, bound 328.5 | 297, bound 324.9 |
| xyz 9×9×9, 300 s | 724, bound 925.7 | 726, bound 902.0 |
| xy 9×9×9, 300 s | 680, bound 973.7 | 709, bound 935.2 |
| xyz 9×9×9 + internal P2Ps, 300 s | 772, bound 922.9 | 780, bound 892.7 |
| xyz 9×9×9, 300 s, `--warm` from the 752 build | | 752, bound 883.9 |
| xyz 9×9×9 + internal P2Ps, 300 s, `--warm` from 778 | | 778, bound 892.0 |

In the LP relaxation alone, `needs_out` lowers the bound from 372.5 to 361.9
on 7×7×7 and from 1004.3 to 972.2 on 9×9×9. The other three families do not
change the LP bound; they help the branch-and-bound. Adding the three dropped
families gave a worse xyz 9×9×9 bound (907.1 against 902.0).

## Open questions

- The LP relaxation mixes whole tile configurations (for example a tile that
  is 60% a cable with tunnels outputting to the shell and 40% a controller).
  Per-tile cuts cannot remove that, so most of the remaining gap is left to
  branching. Stronger relaxations would need inequalities across several
  tiles.
- The cost of the connectivity flow (big-M `link`) was not measured.
- The xyz 9×9×9 gap (752 found, bound 797.9 after the user's 8-hour run) is
  mostly a weak LP relaxation. Tighter constraints are more likely to help
  than more solver time.
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
