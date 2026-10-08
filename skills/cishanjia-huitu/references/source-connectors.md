# Source-specific joined connectors

Use one semantic owner for a connected elbow or fork. Do not split straight
sections into separately movable owners. The source drawing plan must describe
the full route before geometry is generated. Each emitted part remains explicitly
listed once as shaft, dash, head or cap.

`curved_arrow_parts` and `redraw_audit` accept these route forms:

* `points`: the existing four-control cubic.
* `segments`: a list of four-control cubics whose adjacent endpoints coincide.
  Only the last segment gets the owner's declared terminal marker.
* `branches`: flat explicit routes, each declaring `termination` as `arrow`,
  `none` or `inhibition`. A branch may use `points` or `segments`. All branches
  must connect through shared endpoints. Geometry, marker settings and dash
  paint inherit from the owner unless the branch declares a source-specific
  override. Never represent an accidental visual crossing as a branch junction.

An arrow can declare `head_style:"stealth"` with `head_length`, `head_width`
and `head_inset` to match a concave source marker. All lengths must be finite;
length/width positive, inset at least zero and smaller than length. Defaults
retain the previous triangular marker. Measure the source instead of selecting
this shape universally. The complete planned routes, including markers, are
still checked at the unchanged two-source-pixel tolerance.

Example:

```json
{"segments":[[[20,30],[40,30],[60,30],[80,30]],
             [[80,30],[80,40],[80,50],[80,60]]],
 "stroke":"#3d4e6a","stroke_width":3.2,"termination":"arrow",
 "head_style":"stealth","head_length":13,"head_width":10.4,
 "head_inset":3.51}
```

Inspect each isolated connector on a contrasting background; transparent PNGs
must be alpha-composited before making a diagnostic contact sheet. Inspect old
footprints and crossings in the complete scene. Then verify the one whole
native symbol moves without neighboring content. A connected route check cannot
prove biological meaning or justify combining independent source arrows.

Regression coverage: `scripts/tests/test_joined_routes.py` and
`scripts/tests/test_source_markers.py`. These are tool-change tests, not checks
to repeat during every ordinary recreation. No Illustrator connection or API
request is made by those tests.
