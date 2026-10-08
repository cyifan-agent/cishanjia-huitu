# Legacy color analysis: diagnostic only

color_mesh.py approximates source colors with rectangular vector patches. There
is no embedded bitmap, but the output is still a source-color mosaic and does
not satisfy this user's redraw request. It is no longer a final fallback. Its
source-color-mesh marker is rejected by the final redrawing gate; never remove
that marker to bypass the gate.

Retain the helper only for local color-analysis experiments and regression
tests. Masks do not establish clean arrow ownership at crossings or recover
occluded shapes. Do not use them as final group definitions. Follow
[true-vector-redraw.md](true-vector-redraw.md) for the supported construction.

Rebuild shading with coherent editable contours/highlights or adapted glow
layers. Source-specific details and smooth contours require visual review;
pixel resemblance does not establish independent editing or enlarged quality.
