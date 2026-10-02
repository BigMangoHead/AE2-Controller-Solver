#!/usr/bin/env python3
"""
Applied Energistics 2: maximise the channels an ME controller block-structure
can hand out through ME P2P tunnels, inside an N x N x N build volume
(default N = 9).

The build
---------
Every tile of the N x N x N volume is one of

  C  ME Controller     - only allowed in the inner (N-2)^3 block (for N = 9
                         that is the 7 x 7 x 7 limit of a controller structure)
  N  ME cable          - 8 channels (glass / covered / smart cable). Can hold
                         ME P2P tunnels.
  D  ME dense cable    - 32 channels. Cannot hold P2P tunnels.

Controller rules: all controllers form one connected structure, and no
controller may sit in a "cross": it may not have controller neighbours on
both sides along two different axes (so never 5 or 6 controller neighbours,
and never 4 that lie in one plane).

P2P tunnels
-----------
An ME P2P tunnel can be placed on an ME cable (N) on each face that touches a
controller. A cable touching k controllers can therefore hold up to k tunnels.
A tunnel is ONLINE if it gets a channel on the cable network that carries it:
that channel has to be routed through cable tiles to the outer shell of the
volume.

* A cable carries at most 8 channels and a dense cable at most 32. The
  channels used by a cable's own tunnels count towards its 8.
* Outer-shell tiles have unlimited channel capacity.
* Single output direction: every inner cable passes ALL the channels it
  carries (its own tunnels plus everything arriving from other cables) on to
  exactly ONE neighbour, which is another cable or a shell tile. The routing
  is therefore a set of pointer chains leading to the shell.

Tunnels that cannot get a channel are allowed; they just do not count.

Option --enable-internal-p2ps (internal_p2ps): an inner cable (ME or dense)
may also output into a neighbouring controller face. That face is a sink of
unlimited capacity, but it then cannot hold a P2P tunnel. Without the option
a cable may never point at a controller.

The objective is the number of online P2P tunnels. Each one makes
CHANNELS_PER_P2P (32) controller channels accessible, so
accessible channels = 32 x online tunnels.

Symmetry
--------
Only mirror-symmetric builds are considered. --symmetry picks the mirrored
axes (x -> N-1-x, and the same for y and z):

  xy   (default) mirrors in x and y; z is not mirrored. 4 maps.
  xyz  mirrors in x, y and z. 8 maps.

The mirror maps form the group G. Every tile t has a representative rep(t),
found by folding each mirrored coordinate into its lower half, in the region

    REG = { inner tiles t : t_i <= H for every mirrored axis i },   H = (N-1) // 2,

and the model has variables for REG only. REG is the "quarter" for xy
(4 x 4 x 7 = 112 tiles for N = 9) and the "octant" for xyz (4^3 = 64 tiles),
instead of 7^3 = 343.

How the channel routing is modelled
-----------------------------------
* Binary points[a->b] = 1 if cable a outputs towards neighbour b. Each cable
  chooses at most one direction, and a controller chooses none:
      sum_b points[a->b] + ctrl_a <= 1.
  "At most" rather than "exactly" one, because a cable that carries nothing
  can point anywhere and it makes no difference.
* Channels only move along the chosen direction:
      chan[a->b] <= 32 * points[a->b].
* A cable may not point at a controller: points[a->b] + ctrl_b <= 1.
  With internal_p2ps this becomes points[a->b] + p2p[a->b] <= 1: a sink face
  holds no tunnel (p2p is already 0 unless b is a controller).
* Channel conservation at every cable: channels out = channels in + its own
  online tunnels. Channels out is capped at 8 (cable) or 32 (dense cable).
  A pointer cycle cannot bring any tunnel online: nothing can leave the
  cycle, so conservation forces every tunnel feeding it to be offline.
  Cycles therefore never inflate the result, and need no constraint.
  With internal_p2ps the equality becomes out - in - own <= 0 and
  out - in - own + 6 * 32 * ctrl_a >= 0. That is exact at a cable, while a
  controller (out = own = 0) may absorb whatever is sent into its faces.

Symmetry of the routing (an extra restriction)
----------------------------------------------
The pointer field is required to be mirror-symmetric as well, so points, chan
and p2p are stored per canonical arc (rep(a), g(b)), where g maps a to rep(a).
Conservation, the caps and the one-direction rule are written at each REG
tile, summing the canonical variables of all 6 of its full-grid arcs. As a
consequence, a cable lying ON the centre plane of a mirrored axis (odd N)
cannot point across that plane: its two arcs across the plane share one
variable, which then counts twice in the one-direction sum. It can still
point along the plane. With xy, a cable on the centre line x = y = H can only
point along z; with xyz, the centre tile of an odd grid can carry nothing.
This restricts the routing, not the build rules: a symmetric build might in
principle route a little better with an asymmetric pointer field. With the
pointers fixed per direction, averaging over the mirrors no longer works, so
asymmetric routing would need full-grid variables, which this reduced model
deliberately avoids.

Why the rest of the reduction is exact
--------------------------------------
* P2P tunnels. Each tunnel is also stored per canonical arc. The objective
  adds up every tunnel in the full grid, each expressed through its canonical
  variable.
* Cross rule. The rule is G-invariant, so it is enough to impose it at the
  tiles of REG, using the representatives of their neighbours.
* Controller connectivity. Let S be the full controller set and Q = rep(S)
  its image in the quotient graph, whose nodes are REG, with [a]~[b] when
  some images of a and b are adjacent. Then
      S is connected  <=>  Q is connected in the quotient graph
                           AND, for each mirrored axis i, S has a
                           controller in REG's central layer t_i = H.
  (=>) A connected S must cross every mirror plane. For odd N that needs a
       tile on the plane t_i = H. For even N it needs an edge between layers
       H and H+1, which again needs a tile with t_i = H.
  (<=) If Q is connected, G permutes the components of S transitively. A
       controller with t_i = H is fixed by the i-mirror (odd N) or adjacent
       to its own mirror image (even N). Either way the i-mirror maps its
       component to itself. G is abelian, so this holds for every component.
       All the mirrors then fix every component, so there is only one.
  Q's connectivity uses a single-commodity flow from ROOT over the quotient
  graph, and the central-layer conditions are one linear constraint per
  mirrored axis. With the default root at the centre of an odd grid, they
  hold automatically.

Strengthening (CUTS)
--------------------
The LP relaxation on its own is a checkerboard of half-controller,
half-cable tiles, with tunnels on every face and fractional outputs. Four
extra families make it tighter and remove interchangeable solutions. None is
needed for correctness; each keeps at least one optimal solution feasible.
* needs_out (per inner arc k = u->v): p2p[k] <= sum of dir over u's other
  arcs. An online tunnel needs an output, and that output cannot be the
  controller face the tunnel sits on.
* chan_cable (per arc): chan <= 8 * dir + 24 * dense_u. An ME cable passes at
  most 8 along its output; replaces the loose 32 * dir for cables.
* dir_used (per arc): dir <= chan. A direction with no channels can be
  dropped without changing anything else, so only used directions are set.
  This removes interchangeable routings. Channel values in an optimum can be
  taken integral, so a used direction carries at least 1.
* ctrl_nbr (per non-root tile): ctrl_u <= sum of ctrl over u's inner
  neighbours. In a connected structure of 2 or more controllers, every
  controller has a controller neighbour.
Tried and not kept (no gain on 9x9x9): p2p + dir + ctrl_u <= 1 per face; a
head-capacity version of chan_cable; own <= 5 * cable for tiles with no
shell neighbour.

Other choices
-------------
* Outer-shell tiles are fixed as ME cable (N). With unlimited capacity this
  is never worse than dense cable, and their P2P tunnels on the inner
  controllers behind them are online immediately.
* The dense-cable indicator is implicit: dense = 1 - ctrl - cable.
* Tile types and directions are binary. Channel and tunnel variables are
  continuous: once the directions are fixed, the routing is a max-flow along
  the pointer chains with integer capacities, so an integral optimum exists.
"""

import argparse
import itertools
import json
import sys
import time

import pulp

# ----------------------------------------------------------------------------
# Parameters you may want to edit
# ----------------------------------------------------------------------------
N = 9                   # side length of the build volume
SYMMETRY = "xy"         # "xy" (mirror x and y) or "xyz" (mirror all three axes)
ROOT = None             # root controller (any tile; its representative is
                        # used, and all its mirror images become controllers).
                        # None -> centre tile
CABLE_CHANNELS = 8      # channels an ME cable carries
DENSE_CHANNELS = 32     # channels an ME dense cable carries
CHANNELS_PER_P2P = 32   # controller channels one online ME P2P tunnel provides
                        # (only used to report the channel total)
TIME_LIMIT = 600        # seconds
THREADS = None          # None -> solver default
# ----------------------------------------------------------------------------

DIRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
DIR_NAMES = {(1, 0, 0): "+x", (-1, 0, 0): "-x", (0, 1, 0): "+y",
             (0, -1, 0): "-y", (0, 0, 1): "+z", (0, 0, -1): "-z"}
DIR_VECS = {v: k for k, v in DIR_NAMES.items()}

CONTROLLER, CABLE, DENSE = "C", "N", "D"     # tile letters used in builds and files
SYMMETRIES = {"xy": (0, 1), "xyz": (0, 1, 2)}    # --symmetry -> mirrored axes
REGION_NAMES = {"xy": "quarter", "xyz": "octant"}
# Strengthening constraint families (see the docstring). build_model(cuts=...)
# takes a subset, for benchmarking.
CUTS = frozenset({"needs_out", "chan_cable", "dir_used", "ctrl_nbr"})


# ----------------------------------------------------------------------------
# Grid and symmetry helpers
# ----------------------------------------------------------------------------
def is_shell(t, n):
    return any(c == 0 or c == n - 1 for c in t)


def neighbours(t, n):
    x, y, z = t
    for dx, dy, dz in DIRS:
        u = (x + dx, y + dy, z + dz)
        if all(0 <= c < n for c in u):
            yield u


def plane_neighbours(t, axis):
    """The 4 neighbours of t in the plane perpendicular to `axis`."""
    return [(t[0] + d[0], t[1] + d[1], t[2] + d[2]) for d in DIRS if d[axis] == 0]


def mirrors(n, axes):
    """The maps of G (mirror through any subset of the centre planes of the
    mirrored `axes`): 4 maps for xy, 8 for xyz."""
    m = n - 1
    out = []
    for flips in itertools.product((False, True), repeat=len(axes)):
        f = [False] * 3
        for axis, flip in zip(axes, flips):
            f[axis] = flip
        out.append(lambda t, f=tuple(f): tuple(m - t[i] if f[i] else t[i] for i in range(3)))
    return out


def rep(t, n, axes):
    """Representative of tile t in the region (fold every mirrored axis)."""
    return tuple(min(c, n - 1 - c) if i in axes else c for i, c in enumerate(t))


def canon_arc(a, b, n, G, axes):
    """Canonical (tail, head) of the full-grid arc a->b. The tail lies in the
    region; if several mirror maps send a to rep(a), the smallest image of b is
    used so that the choice is deterministic."""
    r = rep(a, n, axes)
    return r, min(g(b) for g in G if g(a) == r)


def extent(n, axes):
    """Largest coordinate of a region tile along each axis (the smallest is 1)."""
    h = (n - 1) // 2
    return [h if axis in axes else n - 2 for axis in range(3)]


def region(n, axes):
    """Tiles with variables: the quarter (xy) or the octant (xyz)."""
    return list(itertools.product(*(range(1, e + 1) for e in extent(n, axes))))


# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------
def build_model(n=N, root=None, cable_channels=CABLE_CHANNELS,
                dense_channels=DENSE_CHANNELS, internal_p2ps=False, symmetry=SYMMETRY,
                cuts=CUTS):
    if n < 3:
        raise ValueError("n must be at least 3")
    h = (n - 1) // 2
    axes = SYMMETRIES[symmetry]
    G = mirrors(n, axes)
    rep_ = lambda t: rep(t, n, axes)
    arc = lambda a, b: canon_arc(a, b, n, G, axes)
    if root is None:
        root = (n // 2, n // 2, n // 2)
    root = tuple(root)
    if is_shell(root, n) or not all(0 <= c < n for c in root):
        raise ValueError(f"root {root} must lie in the inner {(n-2)}^3 block")
    root = rep_(root)

    reg_tiles = region(n, axes)
    inner = [t for t in itertools.product(range(n), repeat=3) if not is_shell(t, n)]
    name = lambda t: f"{t[0]}_{t[1]}_{t[2]}"
    prob = pulp.LpProblem("ae2_controller_p2p", pulp.LpMaximize)

    # --- tile types (region only); dense cable = 1 - ctrl - cable -------------
    ctrl = {t: prob.add_variable(f"ctrl_{name(t)}", cat="Binary") for t in reg_tiles}
    cable = {t: prob.add_variable(f"cable_{name(t)}", cat="Binary") for t in reg_tiles}
    for t in reg_tiles:
        prob += ctrl[t] + cable[t] <= 1, f"type_{name(t)}"
    prob += ctrl[root] == 1, "root_is_controller"
    is_ctrl = lambda t: ctrl[rep_(t)]      # controller indicator of any inner tile

    # --- P2P tunnels: on inner cable u, facing inner controller v ------------
    p2p = {}

    def tunnel(u, v):
        key = arc(u, v)
        if key not in p2p:
            ru, gv = key
            tag = f"{name(ru)}__{name(gv)}"
            var = prob.add_variable(f"p2p_{tag}", 0, 1)
            p2p[key] = var
            prob.addConstraint(var <= cable[ru], f"p2p_on_cable_{tag}")
            prob.addConstraint(var <= ctrl[rep_(gv)], f"p2p_on_ctrl_{tag}")
        return p2p[key]

    # --- channel routing: arcs leave inner tiles, shell tiles are sinks ------
    # chan[key]   = channels passed along an arc
    # points[key] = 1 if the tail cable's single output direction is this arc
    # Both are stored per canonical arc (see docstring).
    chan, points = {}, {}

    def channels(a, b):
        key = arc(a, b)
        if key not in chan:
            ra, gb = key
            tag = f"{name(ra)}__{name(gb)}"
            chan[key] = prob.add_variable(f"chan_{tag}", 0, dense_channels)
            points[key] = prob.add_variable(f"dir_{tag}", cat="Binary")
            # channels only along the chosen direction
            prob.addConstraint(chan[key] - dense_channels * points[key] <= 0,
                               f"chan_dir_{tag}")
            if not is_shell(gb, n):
                if internal_p2ps:
                    # a controller face used as a sink cannot hold a tunnel
                    prob.addConstraint(points[key] + tunnel(a, b) <= 1,
                                       f"sink_or_p2p_{tag}")
                else:
                    # never point a cable at a controller
                    prob.addConstraint(points[key] + ctrl[rep_(gb)] <= 1,
                                       f"dir_not_ctrl_{tag}")
        return chan[key]

    def pointer(a, b):
        channels(a, b)
        return points[arc(a, b)]

    for u in reg_tiles:
        out_u = pulp.lpSum(channels(u, v) for v in neighbours(u, n))
        in_u = pulp.lpSum(channels(w, u) for w in neighbours(u, n) if not is_shell(w, n))
        own = pulp.lpSum(tunnel(u, v) for v in neighbours(u, n) if not is_shell(v, n))
        if internal_p2ps:
            # exact conservation at a cable; a controller (out = own = 0) may
            # absorb whatever its neighbours send into its faces
            prob += out_u - in_u - own <= 0, f"chan_cons_{name(u)}"
            prob += (out_u - in_u - own + 6 * dense_channels * ctrl[u] >= 0,
                     f"chan_sink_{name(u)}")
        else:
            prob += out_u - in_u - own == 0, f"chan_cons_{name(u)}"
        prob += (out_u <= cable_channels * cable[u]
                 + dense_channels * (1 - ctrl[u] - cable[u]), f"chan_cap_{name(u)}")
        prob += own <= cable_channels * cable[u], f"own_p2p_{name(u)}"
        # at most one output direction per cable, none for a controller.
        # Summed over all 6 full-grid arcs: a tile on a centre plane whose two
        # arcs across the plane share one variable would count it twice, so
        # pointing across its own mirror plane is impossible (symmetric routing).
        prob += (pulp.lpSum(pointer(u, v) for v in neighbours(u, n)) + ctrl[u] <= 1,
                 f"one_dir_{name(u)}")

        # --- strengthening: not needed for correctness, but tightens the LP and
        # removes interchangeable solutions (see docstring) ---------------------
        keys = [arc(u, v) for v in neighbours(u, n)]       # with multiplicity
        dense_u = 1 - ctrl[u] - cable[u]
        for k, v in {k: v for k, v in zip(keys, neighbours(u, n))}.items():
            tag = f"{name(k[0])}__{name(k[1])}"
            if "needs_out" in cuts and not is_shell(v, n):
                # an online tunnel needs an output on another face
                prob += (tunnel(u, v) - pulp.lpSum(points[k2] for k2 in keys if k2 != k)
                         <= 0, f"needs_out_{tag}")
            if "chan_cable" in cuts:        # an ME cable passes at most 8 along its output
                prob += (chan[k] - cable_channels * points[k]
                         - (dense_channels - cable_channels) * dense_u <= 0, f"chan_cable_{tag}")
            if "dir_used" in cuts:          # no output direction without channels
                prob += points[k] - chan[k] <= 0, f"dir_used_{tag}"
        if "ctrl_nbr" in cuts and u != root:
            # a non-root controller has a controller neighbour
            prob += (ctrl[u] - pulp.lpSum(is_ctrl(v) for v in neighbours(u, n)
                                          if not is_shell(v, n)) <= 0, f"ctrl_nbr_{name(u)}")

    # --- controller cross rule and max 4 controller neighbours ---------------
    for v in reg_tiles:
        for axis in range(3):
            pn = plane_neighbours(v, axis)
            if all(not is_shell(p, n) for p in pn):
                prob += (ctrl[v] + pulp.lpSum(is_ctrl(p) for p in pn) <= 4,
                         f"cross_{name(v)}_{axis}")
        nb = [p for p in neighbours(v, n) if not is_shell(p, n)]
        if len(nb) >= 5:
            prob += (pulp.lpSum(is_ctrl(p) for p in nb) + (len(nb) - 4) * ctrl[v]
                     <= len(nb), f"deg_{name(v)}")

    # --- controller connectivity: flow from root on the quotient graph -------
    qedges = set()
    for u in inner:
        for v in neighbours(u, n):
            if not is_shell(v, n):
                ru, rv = rep_(u), rep_(v)
                if ru != rv:
                    qedges.add((ru, rv))
    M = len(reg_tiles) - 1
    link = {}
    for (a, b) in sorted(qedges):
        if b == root:
            continue
        var = prob.add_variable(f"link_{name(a)}__{name(b)}", 0, M)
        link[a, b] = var
        prob += var <= M * ctrl[a], f"link_a_{name(a)}__{name(b)}"
        prob += var <= M * ctrl[b], f"link_b_{name(a)}__{name(b)}"
    for v in reg_tiles:
        if v == root:
            continue
        inflow = pulp.lpSum(var for (a, b), var in link.items() if b == v)
        outflow = pulp.lpSum(var for (a, b), var in link.items() if a == v)
        prob += inflow - outflow - ctrl[v] == 0, f"conn_{name(v)}"
    for axis in axes:
        prob += (pulp.lpSum(ctrl[t] for t in reg_tiles if t[axis] == h) >= 1,
                 f"central_layer_{axis}")

    # --- objective: all online P2P tunnels in the full grid ------------------
    obj = []
    for u in inner:
        for v in neighbours(u, n):
            if not is_shell(v, n):
                obj.append(tunnel(u, v))             # on inner cable u, facing controller v
        k = sum(1 for w in neighbours(u, n) if is_shell(w, n))
        if k:
            obj.append(k * is_ctrl(u))               # on shell cables, facing controller u
    prob += pulp.lpSum(obj)

    meta = dict(n=n, root=root, region=reg_tiles, ctrl=ctrl, cable=cable,
                points=points, G=G, axes=axes, symmetry=symmetry,
                internal_p2ps=internal_p2ps)
    return prob, meta


def extract_directions(meta):
    """Output direction of every inner cable on the full grid ('+x', ... or
    None for a cable that carries no channels)."""
    n, points, G, axes = meta["n"], meta["points"], meta["G"], meta["axes"]
    dirs = {}
    for t in itertools.product(range(1, n - 1), repeat=3):
        dirs[t] = None
        for v in neighbours(t, n):
            var = points.get(canon_arc(t, v, n, G, axes))
            if var is not None and (var.value() or 0) > 0.5:
                dirs[t] = DIR_NAMES[tuple(v[i] - t[i] for i in range(3))]
    return dirs


def extract_build(meta):
    """Expand the region solution to the full build volume."""
    n = meta["n"]
    build = {}
    for t in itertools.product(range(n), repeat=3):
        if is_shell(t, n):
            build[t] = CABLE
        else:
            r = rep(t, n, meta["axes"])
            if (meta["ctrl"][r].value() or 0) > 0.5:
                build[t] = CONTROLLER
            elif (meta["cable"][r].value() or 0) > 0.5:
                build[t] = CABLE
            else:
                build[t] = DENSE
    return build


def is_symmetric(build, n, axes):
    return all(build[t] == build[g(t)] for t in build for g in mirrors(n, axes))


# ----------------------------------------------------------------------------
# Independent verification on the FULL grid: check the controller rules and
# recount the online P2P tunnels with an exact max-flow (networkx). Uses
# nothing from the MILP.
#
# With `dirs` (each inner cable's single output direction), every cable may
# only pass channels to the one neighbour it points at. The channel graph is
# then a forest of pointer chains, and its max-flow is the best tunnel count
# for that build AND that routing.
# Without `dirs`, cables may split their channels freely, which gives an upper
# bound for the build (not achievable in general under the one-direction rule).
#
# With `internal_p2ps`, a cable may also point at a controller: that face is
# then a sink of unlimited capacity and holds no tunnel. Without `dirs`, every
# controller face counts as both a sink and a tunnel (still an upper bound).
# ----------------------------------------------------------------------------
def count_online_p2p(build, n, dirs=None, cable_channels=CABLE_CHANNELS,
                     dense_channels=DENSE_CHANNELS, internal_p2ps=False):
    """Return (online P2P tunnels, list of rule violations)."""
    import networkx as nx

    controllers = [t for t, s in build.items() if s == CONTROLLER]
    errors = []
    for t in controllers:
        if is_shell(t, n):
            errors.append(f"controller on shell at {t}")
    cs = set(controllers)
    if controllers:
        seen, stack = {controllers[0]}, [controllers[0]]
        while stack:
            u = stack.pop()
            for v in neighbours(u, n):
                if v in cs and v not in seen:
                    seen.add(v)
                    stack.append(v)
        if len(seen) != len(cs):
            errors.append("controllers not connected")
    for t in controllers:
        cn = [v for v in neighbours(t, n) if v in cs]
        if len(cn) >= 5:
            errors.append(f"controller {t} has {len(cn)} controller neighbours")
        for axis in range(3):
            if all(p in cs for p in plane_neighbours(t, axis)):
                errors.append(f"cross at {t} in plane normal to axis {axis}")

    net = nx.DiGraph()
    S, T = "S", "T"
    for t, s in build.items():
        if s == CONTROLLER:
            continue
        sink_face = False
        if is_shell(t, n):
            net.add_edge(("in", t), T)                    # unlimited, channels have arrived
        else:
            cap = cable_channels if s == CABLE else dense_channels
            net.add_edge(("in", t), ("out", t), capacity=cap)
            if dirs is None:
                targets = [v for v in neighbours(t, n) if build[v] != CONTROLLER]
                if internal_p2ps and len(targets) < len(list(neighbours(t, n))):
                    net.add_edge(("out", t), T)           # some controller face as sink
            else:
                targets = []
                d = dirs.get(t)
                if d is not None:
                    v = tuple(t[i] + DIR_VECS[d][i] for i in range(3))
                    if build[v] != CONTROLLER:
                        targets = [v]
                    elif internal_p2ps:
                        net.add_edge(("out", t), T)       # controller face is the sink
                        sink_face = True
                    else:
                        errors.append(f"cable {t} points at controller {v}")
            for v in targets:
                net.add_edge(("out", t), ("in", v))
        if s == CABLE:
            k = sum(1 for v in neighbours(t, n) if build[v] == CONTROLLER) - sink_face
            if k:
                net.add_edge(S, ("in", t), capacity=k)    # one tunnel per controller face
    if S not in net:
        return 0, errors
    val, _ = nx.maximum_flow(net, S, T)
    return val, errors


# ----------------------------------------------------------------------------
# Solving helpers (work with PuLP 3.x and 4.x)
# ----------------------------------------------------------------------------
def make_cbc(**kw):
    """CBC solver. PuLP 3 bundles it as PULP_CBC_CMD; PuLP 4 dropped that and
    uses COIN_CMD, which needs a separately installed `cbc` executable."""
    cls = getattr(pulp, "PULP_CBC_CMD", None) or pulp.COIN_CMD
    return cls(**kw)


def make_solver(name, msg, time_limit, threads, warm=False):
    """`warm`: start from the variables' current values."""
    kw = dict(msg=msg, timeLimit=time_limit)
    if warm:
        kw["warmStart"] = True
    if threads:
        kw["threads"] = threads
    return pulp.HiGHS(**kw) if name == "highs" else make_cbc(**kw)


def solve_outcome(prob, result):
    """(proven_optimal, best_bound) after prob.solve(), for PuLP 3 and 4."""
    h = getattr(prob, "solverModel", None)
    if h is not None and hasattr(h, "getModelStatus"):
        import highspy
        optimal = h.getModelStatus() == highspy.HighsModelStatus.kOptimal
        bound = h.getInfo().mip_dual_bound
        if bound < 0:          # maximisation passed to HiGHS as min of -objective
            bound = -bound
        return optimal, bound
    if hasattr(result, "has_solution"):                     # PuLP 4
        return int(result.status) == 1, getattr(result, "best_bound", None)
    return getattr(prob, "sol_status", result) == 1, None   # PuLP 3


# ----------------------------------------------------------------------------
# Large-neighbourhood search inside the region
# ----------------------------------------------------------------------------
def fix_to_build(meta, build, free=()):
    """Fix every region tile's type to `build`, except the tiles in `free`."""
    free = set(free)
    for t in meta["region"]:
        for var, s in ((meta["ctrl"][t], CONTROLLER), (meta["cable"][t], CABLE)):
            if t in free:
                var.lowBound, var.upBound = 0, 1
            else:
                var.lowBound = var.upBound = (1 if build[t] == s else 0)
    if meta["root"] in free:
        meta["ctrl"][meta["root"]].lowBound = 1


def save(path, n, root, build, dirs, tunnels, symmetry, internal_p2ps=False, **extra):
    with open(path, "w") as fh:
        json.dump({"n": n, "root": root, "symmetry": symmetry,
                   "internal_p2ps": internal_p2ps, **extra,
                   "online_p2p_tunnels": tunnels,
                   "accessible_channels": tunnels * CHANNELS_PER_P2P,
                   "layout": {f"{x},{y},{z}": s for (x, y, z), s in build.items()},
                   "directions": {f"{x},{y},{z}": d for (x, y, z), d in dirs.items()
                                  if d is not None}},
                  fh, indent=1)


def solve_fixed(prob, meta, build, free, solver, sub_time, threads):
    """Solve with every region tile outside `free` fixed to `build`. Directions
    stay free everywhere. Returns (build, directions, verified tunnels) or None."""
    fix_to_build(meta, build, free)
    prob.solve(make_solver(solver, False, sub_time, threads))
    if prob.objective.value() is None:
        return None
    cand, dirs = extract_build(meta), extract_directions(meta)
    tunnels, errs = count_online_p2p(cand, meta["n"], dirs,
                                     internal_p2ps=meta["internal_p2ps"])
    return None if errs else (cand, dirs, tunnels)


def lns(prob, meta, build, iters, window, sub_time, solver, threads, seed, out, log=print):
    """Repeatedly free a random box of region tiles, keep the rest fixed, and
    solve that sub-MILP (directions are re-optimised everywhere each time)."""
    import random
    rng = random.Random(seed)
    n = meta["n"]
    ext = extent(n, meta["axes"])
    # best routing for the starting build (also handles files without directions)
    start = solve_fixed(prob, meta, build, [], solver, max(sub_time, 60), threads)
    if start is None:
        sys.exit("could not route the starting build")
    build, dirs, best = start
    log(f"LNS start: {best} online P2P tunnels")
    for it in range(iters):
        w = [min(rng.choice(window), e) for e in ext]
        corner = [rng.randint(1, e - wi + 1) for e, wi in zip(ext, w)]
        free = [t for t in meta["region"]
                if all(corner[i] <= t[i] < corner[i] + w[i] for i in range(3))]
        res = solve_fixed(prob, meta, build, free, solver, sub_time, threads)
        if res is not None and res[2] >= best:
            if res[2] > best:
                log(f"  iter {it}: {best} -> {res[2]}   (window {w} at {corner})")
                save(out, n, meta["root"], res[0], res[1], res[2], meta["symmetry"],
                     internal_p2ps=meta["internal_p2ps"])
            build, dirs, best = res
    fix_to_build(meta, build, meta["region"])    # release all bounds
    return build, dirs, best


def load_build(path):
    """Read a saved solution. Returns (n, build, directions or None)."""
    with open(path) as fh:
        data = json.load(fh)
    key = lambda k: tuple(int(v) for v in k.split(","))
    build = {key(k): s for k, s in data["layout"].items()}
    dirs = None
    if "directions" in data:
        dirs = {key(k): d for k, d in data["directions"].items()}
    return data["n"], build, dirs


ARROWS = {"+x": ">", "-x": "<", "+y": "v", "-y": "^", "+z": "+", "-z": "-", None: "."}


def print_build(build, n, dirs=None, file=sys.stdout):
    """Tile types (left) and, if given, cable output directions (right).
    Rows are y (downwards), columns are x.
    Tiles:   C ME Controller   N ME cable (8 ch)   D ME dense cable (32 ch)
    Arrows:  > +x   < -x   v +y   ^ -y   + +z (next layer)   - -z (previous layer)
             C controller,  . carries no channels,  # shell"""
    print("tiles:  C = ME Controller, N = ME cable (8 channels), "
          "D = ME dense cable (32 channels)", file=file)
    if dirs is not None:
        print("cable output directions:  > +x  < -x  v +y  ^ -y  + +z  - -z  "
              "(C controller, . unused, # shell)", file=file)
    print(file=file)
    for z in range(n):
        print(f"z = {z}", file=file)
        for yy in range(n):
            row = " ".join(build[(x, yy, z)] for x in range(n))
            if dirs is not None:
                arr = []
                for x in range(n):
                    t = (x, yy, z)
                    arr.append("#" if is_shell(t, n) else
                               "C" if build[t] == CONTROLLER else ARROWS[dirs.get(t)])
                row += "     " + " ".join(arr)
            print("  " + row, file=file)
        print(file=file)


def describe(tunnels):
    return (f"{tunnels} online P2P tunnels "
            f"= {tunnels * CHANNELS_PER_P2P} accessible channels")


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=N,
                    help="side length of the build volume (default 9)")
    ap.add_argument("--root", type=int, nargs=3, default=ROOT,
                    help="root controller x y z (default: centre)")
    ap.add_argument("--time-limit", type=float, default=TIME_LIMIT)
    ap.add_argument("--threads", type=int, default=THREADS)
    ap.add_argument("--solver", choices=["highs", "cbc"], default="highs")
    ap.add_argument("--out", default="solution.json")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--lns", type=int, default=0, metavar="ITERS",
                    help="after the full solve (or starting from --init), run ITERS "
                         "rounds of large-neighbourhood search")
    start = ap.add_mutually_exclusive_group()
    start.add_argument("--init", help="start LNS from this solution JSON (skips the full solve)")
    start.add_argument("--warm", metavar="FILE",
                       help="start the full solve from this solution JSON (warm start)")
    ap.add_argument("--window", type=int, nargs="+", default=[2, 3],
                    help="LNS box side lengths (inside the region) to sample from")
    ap.add_argument("--sub-time", type=float, default=20, help="time limit per LNS sub-MILP")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--symmetry", choices=sorted(SYMMETRIES), default=SYMMETRY,
                    help="mirror symmetry of the build: xy (x and y only) or xyz "
                         "(all three axes) (default %(default)s)")
    ap.add_argument("--enable-internal-p2ps", action="store_true",
                    help="let inner cables output into a controller face (a sink of "
                         "unlimited capacity); that face then cannot hold a P2P tunnel")
    args = ap.parse_args()
    say = lambda s: print(s, flush=True)

    t0 = time.time()
    sinks = args.enable_internal_p2ps
    sym, axes = args.symmetry, SYMMETRIES[args.symmetry]
    prob, meta = build_model(args.n, args.root, internal_p2ps=sinks, symmetry=sym)
    region_name = REGION_NAMES[sym]
    say(f"model: {len(prob.variables())} variables, {prob.numConstraints()} constraints "
        f"(built in {time.time()-t0:.1f}s), symmetry: {sym}, "
        f"{region_name} tiles = {len(meta['region'])}, "
        f"root controller ({region_name} representative) = {meta['root']}, "
        f"controller faces as sinks: {sinks}")

    def load_start(path):
        n0, build, _ = load_build(path)           # routing is recomputed
        if n0 != args.n:
            sys.exit("the initial solution has a different grid size")
        if not is_symmetric(build, args.n, axes):
            sys.exit(f"the initial solution is not {sym}-symmetric")
        if build[meta["root"]] != CONTROLLER:
            sys.exit(f"root {meta['root']} is not a controller in the initial solution")
        return build

    dirs = None
    if args.init:
        build = load_start(args.init)
    else:
        if args.warm:
            # route the start build with its tile types fixed, so that every
            # variable has a value, then release the bounds and pass it to HiGHS
            start = solve_fixed(prob, meta, load_start(args.warm), [], args.solver,
                                max(args.sub_time, 120), args.threads)
            if start is None:
                sys.exit("could not route the warm-start build")
            fix_to_build(meta, start[0], meta["region"])
            say(f"warm start: {start[2]} online P2P tunnels")
        t0 = time.time()
        result = prob.solve(make_solver(args.solver, not args.quiet,
                                        args.time_limit, args.threads, warm=bool(args.warm)))
        solve_time = time.time() - t0
        if prob.objective.value() is None:
            say("no feasible solution found")
            return
        obj = prob.objective.value()
        optimal, bound = solve_outcome(prob, result)
        status = (f"optimal among {sym}-symmetric builds" if optimal
                  else "feasible (limit reached, not proven optimal)")
        say(f"status: {status}   solve time {solve_time:.1f}s")
        if bound is not None:
            say(f"best bound: {bound:.1f} tunnels   gap: {bound - obj:.1f}")
        build, dirs = extract_build(meta), extract_directions(meta)
        tunnels, errors = count_online_p2p(build, args.n, dirs, internal_p2ps=sinks)
        say(f"MILP objective: {obj:.1f} online P2P tunnels")
        say(f"verified on the full grid (independent max-flow along the chosen "
            f"directions): {describe(tunnels)}   "
            f"controllers: {sum(s == CONTROLLER for s in build.values())}")
        say(f"rule violations: {errors or 'none'}")
        save(args.out, args.n, meta["root"], build, dirs, tunnels, sym, internal_p2ps=sinks,
             objective=obj, status=status, bound=bound)
        say(f"wrote {args.out}")

    if args.lns or dirs is None:
        build, dirs, _ = lns(prob, meta, build, args.lns, args.window, args.sub_time,
                             args.solver, args.threads, args.seed, args.out, log=say)

    tunnels, errors = count_online_p2p(build, args.n, dirs, internal_p2ps=sinks)
    say(f"final verified result: {describe(tunnels)}   violations: {errors or 'none'}   "
        f"{sym}-symmetric: {is_symmetric(build, args.n, axes)}")
    print_build(build, args.n, dirs)


if __name__ == "__main__":
    main()
