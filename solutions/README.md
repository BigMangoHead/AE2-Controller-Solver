# Best Solutions

Note that *.json is the file accepted by the solver, and can be used to warm up
the MILP by using --warm. The *.txt is meant to be human readable, showing each
layer of the controller, indicating D for dense cable, N for normal cable, and
C for controller. Every face of a normal cable pointing into an ME controller 
should then have a P2P placed on it.

The *.json file also documents the upper bound that the MILP found while attempting
to solve with the given conditions.

## Solution Descriptions

symmetric-OPTIMAL shows the optimal ME controller design, assuming mirror-symmetry
around the central x, y, and z planes, and disallowing internal P2Ps. It has
752 P2Ps.

symmetric-internal-OPTIMAL shows the optimal ME controller design, assuming
mirror-symmetry around the central x, y, and z planes, and allowing internal P2Ps.
It has 780 P2Ps.

xy-symmetric-internal shows the best ME controller I have found thus far, assuming
mirror-symmetry around the central x and y planes, and allowing internal P2Ps. It
has 785 P2Ps.

no-symmetry-best shows the best design I have found with no internal P2Ps, and
has 761 P2Ps.

I believe I had a nosymmetry solve with internal P2Ps for 791, but I can't find it
at the moment.

## On Finding These
I limited to xyz mirror symmetry because it makes for nice designs, and the current
linear system is not optimized enough for it to be computationally possible for me
to solve it when there is no symmetry. This is mainly due to a lack of RAM, not 
of computation time (getting symmetric-OPTIMAL took 30 hours and peaked at ~10GB of RAM).

The best solutions I've found have been using the LNS mode of the solver on an
existing symmetric solve.

