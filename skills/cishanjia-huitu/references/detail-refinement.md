# Source detail, typography and local revisions

Use these tools after inspecting the actual reference. They strengthen measured
construction and review; they install no neural model. Never turn a passing
declaration/count test into a claim of visual equivalence.

## Landmarks that survive fitting

Measure the actual silhouette in source pixels. Include lobes, indentations,
tips and contact points. Keep points ordered along one contour; omit the duplicate
closing point. Mark a notch corner as `corner`, a smooth extremity as `smooth`.
Sparse deliberate measurements are preferable to sending every staircase pixel.

```json
{"schema":"landmark-contour-v1","object_id":"dying-cell",
 "closed":true,"tolerance_px":0.45,"spacing_px":0.5,
 "points":[[30,30],[75,30],[75,55],[95,55],[95,30],[140,30],[140,100],[30,100]],
 "landmarks":[{"index":0,"kind":"corner","name":"upper-left"},
 {"index":1,"kind":"corner"},{"index":2,"kind":"corner","name":"notch-left"},
 {"index":3,"kind":"corner","name":"notch-right"},{"index":4,"kind":"corner"},
 {"index":5,"kind":"corner"},{"index":6,"kind":"corner"},{"index":7,"kind":"corner"}]}
```

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\refine_contour.py" --landmarks contour-measurements.json --output contour-fit.json
```

The output supplies authored cubic `d`, fixed landmarks, segment count and the
actual anchor shift from coordinate rounding. Place the path in its semantic
owner and record `construction:"curve-refit"`. A smooth anchor constrains joining
tangents; a corner retains separate incoming/outgoing directions. Coarse sampling
retains measured vertices. Fitting does not discover internal anatomy. Overlay
the refitted outline on the source for internal QA and inspect the concavities;
the delivered canvas contains only the redrawn vectors.

## Declare complete biological features

For new detailed figures set `feature_contract:"source-features-v1"` in
drawing-plan.json. Each cell, organelle, DNA, molecule, protein or complex gets a
nonempty `required_features` inventory and `features`. Backgrounds, captions and
connectors retain their existing plan contract. Example object record:

```json
{"id":"dying-cell","construction":"curve-refit",
 "reference_features":["asymmetric rim, nucleus, blebs and interior vesicles"],
 "parts":[{"id":"cell-body","role":"shape"},{"id":"cell-nucleus","role":"detail"},
 {"id":"cell-vesicle-1","role":"detail"},{"id":"cell-vesicle-2","role":"detail"}],
 "required_features":["body","nucleus","vesicles"],
 "features":[
 {"key":"body","part_ids":["cell-body"],"expected_parts":{"min":1,"max":1},
  "source_bbox_px":[30,30,110,70],"max_bbox_error_px":2,
  "landmarks":[{"point":[75,55],"kind":"boundary","name":"defining-notch","max_error_px":2}]},
 {"key":"nucleus","part_ids":["cell-nucleus"],"expected_parts":{"min":1,"max":1}},
 {"key":"vesicles","part_ids":["cell-vesicle-1","cell-vesicle-2"],"expected_parts":{"min":2,"max":2}}]}
```

Assign each biological graphic once to a primary feature; text is exempt from
this feature coverage rule but still has one semantic owner. Do not count the
same shape twice to satisfy two missing anatomical features. One feature may
own several meaningful paths, including both broken DNA duplexes and every
associated shard. A compound outline with several lobes can remain one part.
`expected_parts` counts declared vector parts, not automatically recognized
vesicles, beads, rungs or anatomical structures. Derive these counts by inspection.

Use source bounds and boundary landmarks for contour-critical features, and
`kind:"inside"` for landmarks that must lie inside a particular shape. Bounds
are `[x,y,width,height]`. Checks render only those feature parts with their parent
transforms and native paint. Boundary points refer to that feature's visible
alpha boundary; for a filled cell body the notch is visible, whereas an internal
crista needs a separate feature/part. Choose meaningful source tolerances before
comparison. Equal outer bounds cannot excuse a missing notch.

`feature_audit.py --svg master.svg --plan drawing-plan.json --report features.json`
runs independently. `redraw_audit.py` invokes it whenever feature_contract is set
and forwards failures to quality_gate.py. Missing required features, foreign
parts, double-assigned primary parts, count violations, inaccurate bounds and
missed landmarks fail. These checks cannot identify an inaccurately inventoried
biological motif or prove membrane topology. Inspect the source and enlarged
replica, including interiors, with an object-level defect list.

## Coherent live typography

Assign the same `style_group` to labels that visibly share a source family. Keep
bold, italic, color and baselines on each individual run. Titles, body labels and
special notation can have distinct groups when the reference warrants it.
Without style_group, the fitter groups the original declared family/weight/style;
existing manifests remain compatible.

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\fit_text.py" --source reference.png --cleaned diagnostic-background.png --manifest text.json --families "Arial,Arial Narrow,Times New Roman" --width-adjustment 0.02 --output fitted-text.json --report typography-fit.json
```

This fits already transcribed labels without OCR, selecting one family per group
using combined glyph error. It preserves run content, weight/style and source
order, and permits a controlled horizontal-width adjustment (0 to 0.12). Keep
the default small; large stretching can disguise the wrong family. The diagnostic
cleaned background must retain nontext graphics for fitting but is never inserted
in the deliverable. Check fitted text against the source and the actual native
export. A low glyph error over overlapping graphics is not reliable evidence.

## Whole components and object-local revisions

Extract a complete owner from a reviewed construction master:

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\scene_patch.py" extract --svg master.svg --plan drawing-plan.json --object-id mitochondrion-1 --output-svg mitochondrion-component.svg --output-plan mitochondrion-component.json --report component-review.json
```

The component retains all of that owner's graphic parts, text, paint resources,
feature declarations and the source pixel canvas. Reuse this as editable
construction material, then adapt its contour, pose, internal anatomy, counts and
labels. It is not an automatically correct icon for a new source. Keep distinct
semantic IDs/symbol definitions for separately editable objects.

For a local revision, supply both current SHA256 hashes, unique existing owner
IDs and explicit operations. Replacement paths are relative to the patch file.

```json
{"schema":"scene-patch-v1","base_svg_sha256":"CURRENT_SVG_SHA256",
 "base_plan_sha256":"CURRENT_PLAN_SHA256","operations":[
 {"op":"replace","object_id":"mitochondrion-1",
  "source_svg":"mitochondrion-component.svg","source_plan":"mitochondrion-component.json"},
 {"op":"translate","object_id":"arrow-2","dx":3,"dy":-2}]}
```

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\scene_patch.py" patch --svg master.svg --plan drawing-plan.json --patch local-patch.json --output-svg master-revision-2.svg --output-plan plan-revision-2.json --report local-revision.json
```

Outputs must be new paths. Replacement retains the same owner ID, source canvas
and paint order. Paint IDs are isolated so a changed organelle cannot recolor a
neighbor that shared the old gradient. Unchanged sibling vectors and plan entries
must remain identical. Translating an arrow updates its declared route; source
feature bounds/landmarks remain source measurements, so moving away from the
reference will still be detected. The patch report invalidates prior review.

This edits construction files only; it never silently modifies the existing
Illustrator document. Re-run feature/connector audits, regional comparison and
visual review on the new master, then bind new QA hashes. Any native delivery
still needs permission already implied by the drawing request, preservation of
existing artwork and actual Illustrator export/movement verification.

## Learn from a resolved failure

Record object ID, observed difference, cause, correction and verification. For
example: `cell-1 / notch flattened / unconstrained smoothing / fixed corner
anchors / boundary landmark and enlarged visual review pass`. Keep the reference
and original tolerances. Add a synthetic behavioral regression for a repeatable
tool defect. Update the smallest relevant instruction/tool; never turn one
source's anatomy into a default motif for all future figures.
