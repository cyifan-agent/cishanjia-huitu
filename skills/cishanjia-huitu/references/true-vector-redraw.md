# Authored redraw contract

The reference is a measurement and inspection aid. Recreate every foreground
object with meaningful curves, fills, strokes and live text. Source-specific
construction is mandatory: shape, pose, feature topology and visual treatment
must be adapted from the source rather than a generic biology icon.

## Plan and construction

Before Illustrator drawing, prepare the whole layout, per-object feature list,
parts and connector routes. Use source pixel coordinates. Measure landmarks and
tangents for cubic paths; do not assign ownership by proximity, hue, masks or
rectangular windows. At an overlap, draw the entire arrow and complete shapes
behind the overlap, then establish paint order. Moving a shape should not reveal
another baked copy or a hole in the compartment.

Draw closed contours for bodies and anatomical regions, smooth curves for
membranes/cristae/strands and independent strokes for arrows. Highlights and
shadows are coherent vector shapes or native gradient paint inside their owner.
For elliptical halos, prefer one ellipse with a radial gradient; stacked glow
layers are a diagnostic approximation and not this user's delivery. Irregular
shading needs adapted contours. Do not convert shading pixels into rectangles. A local trace can help
measure a single contour, then be refitted and reviewed; record curve-refit.

One connector is one editing group. It owns shaft/dashes/head/cap only. A nearby
label or molecule is a separate object even if its color matches. Protein labels
belong to the protein. Complexes may retain internal protein subgroups without
additional semantic-owner markers. DNA owns its strands, rungs and fragments.

## Drawing-plan schema

Master root: `data-huitu-grouping="semantic-v1"` and
`data-huitu-build="vector-redraw-v1"`. The marker is a declaration, not proof;
the actual geometry, construction review and isolation checks are still required.
Every direct object group appears exactly once in drawing-plan.json. Every
drawable's actual ID appears exactly once in that object's parts list.

```json
{"schema":"vector-redraw-v1","canvas":[600,400],"objects":[
 {"id":"background","construction":"authored",
  "reference_features":["continuous lavender cytoplasm"],
  "parts":[{"id":"bg-fill","role":"shape"}]},
 {"id":"arrow-1","construction":"authored",
  "reference_features":["curved green activation; independent of nearby protein"],
  "parts":[{"id":"arrow-1-shaft","role":"shaft"},{"id":"arrow-1-head","role":"head"}],
  "connector":{"points":[[100,100],[150,80],[170,160],[220,150]],
   "stroke":"#20b65d","stroke_width":3,"head":12,
   "termination":"arrow","dashed":false}}
]}
```

Root-level defs may contain only native linearGradient/radialGradient definitions
and ordered color stops. Internal `fill="url(#paint-id)"` or stroke references
are allowed; no external resource, filter, image or mesh. Resource stops are paint
metadata, not separate movable artwork or entries in vector-part ownership.
One gradient-filled silhouette remains one vector part. native_gradients.py and
compose_scene.py (`native_glow`, or explicit `gradients`) construct this form.
contour_refit.py fits one measured silhouette to smooth cubics without replacing
its defining lobes by a generic ellipse or stellated icon.

New detailed biological plans also declare `feature_contract:"source-features-v1"`.
See [detail-refinement.md](detail-refinement.md) for required_features, primary
part assignment, measured bounds/landmarks and anchored contour fitting. The
feature audit is integrated into redraw_audit.py; legacy plan compatibility does
not waive the new inventory for a fresh detailed recreation.

Other part roles: outline, detail, shading, highlight, text. Connectors allow
only shaft, dash, head and cap roles. A straight arrow uses four collinear
controls. Inhibition uses `termination:"inhibition",cap_width:18`; an uncapped
leader uses `termination:"none"`. Dashed curves include positive dash/gap
lengths and individually declared dash IDs. `curved_arrow_parts` in
compose_scene.py expands these parts without pixel extraction.

For connected elbow/fork routes and measured concave arrowheads, see
[source-connectors.md](source-connectors.md). Keep the whole route in one owner;
segment/branch support does not relax connector isolation or route tolerances.

## Acceptance

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\redraw_audit.py" --svg master.svg --plan drawing-plan.json --artifacts connector-checks --report redraw-audit.json
& $taskPy -X utf8 "$taskSkill\scripts\quality_gate.py" --svg master.svg --drawing-plan drawing-plan.json --comparison comparison.json --review visual-review.json --output quality-gate.json
```

Inspect every connector-checks/*-isolated.png: it contains just the intended
arrow/T-bar, including all dashes, no molecule, lettering or background patch.
Inspect the corresponding hidden/moved SVG in the full scene: neighboring
objects remain complete and at their original positions. The automated route
test tolerates two source pixels of geometric/antialias difference and rejects
marks outside the expected route. It does not recognize anatomy or certify
every mark at a crossing. Record actual inspection, not merely a test result.

Also compare source/replica enlarged crops: smooth silhouette, source-specific
interior features, convincing coherent shading and correct typography. Pixel
scores measure regression, not redraw quality. Record vector_construction,
connector_isolation and shape_editability evidence in addition to the existing
appearance and grouping checks. The gate requires a bound drawing plan and
rejects diagnostic meshes even if those checks were mistakenly marked pass.

After authorized native drawing, test actual movement in a temporary copy with
verify_native_editability.ps1. In default symbol mode every biological object and
connector is tested. Remove the outer group, repeat ordinary ungroup five times,
then move each whole instance and verify all parts/text follow while neighboring
bounds stay fixed. Inspect gradients, including stroke paint, only in disposable
expanded copies. Close only the temporary document; inspect old footprints too.

For skills-only updates, use synthetic fixtures and mocks; do not call Illustrator
or redraw the user's figure. Do not infer proprietary model weights or promise
Cell-LCT quality from software checks.
