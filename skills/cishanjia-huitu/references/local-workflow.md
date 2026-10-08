# Local redrawing tools

Use scripts/runtime_env.py to locate Python packages configured in
runtime.local.json. Keep local runtime paths unchanged; Drawing uses local packages and no remote image API or credentials.
For a fresh installation, run scripts/setup_runtime.py once as described in
installation.md; it installs declared packages from PyPI into this skill only.

Use [efficient-workflow.md](efficient-workflow.md) by default. The commands below
share one local exact-render cache; a hit reuses diagnostic pixels, while every
logical check and bound final review still runs.

## Construction

Prepare drawing-plan.json as defined in true-vector-redraw.md. compose_scene.py
accepts canvas:{width,height} and objects:[...] ordered by z. Supported primitives
include path, ellipse, rect, polygon, line, arrow, curved_arrow, native_glow and text.
Use native_gradients.py for authored native fills. Legacy soft_glow produces
many opacity ellipses and is diagnostic only for this user's editing workflow.
Choose source-specific contours over generic motifs. A plan's connector uses
four cubic points, stroke_width, color and termination arrow/inhibition/none.
Use cap_width for a T-bar. Preserve each vector part's ID.

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\compose_scene.py" --manifest scene.json --output independent-parts.svg
& $taskPy -X utf8 "$taskSkill\scripts\object_groups.py" --svg independent-parts.svg --manifest objects.json --output master.svg --report object-groups.json
```

Set data-huitu-build="vector-redraw-v1" only for a reviewed authored redraw,
not to reclassify automatic source-color output. The plan declares every group's
construction (authored/curve-refit), source features and actual part IDs/roles.
local_reconstruct.py and color_mesh.py remain diagnostic helpers. Whole-image
traces and color-patch mosaics are not final artwork, regardless of similarity.

For live text, manifest entries specify id, content, object_id, bbox_px, x/y
baseline, source_font_size_px, horizontal_scale, font_family, font_weight,
font_style, fill and text_anchor. Keep separate lines/styled runs as separate text
nodes. manifest_lint.py validates schema; fit_text.py fits declared labels against
glyph pixels without OCR. The background delivered is drawn geometry, not the
diagnostic cleaned raster. Native import resolves exact family and weight.

For anchor-preserving contour fitting, primary feature declarations, coherent
font groups and whole-object extraction/revisions, read
[detail-refinement.md](detail-refinement.md). Use refine_contour.py for explicit
corner/smooth measurements, feature_audit.py for the source-features-v1 contract,
and scene_patch.py for hash-bound new construction revisions. New detailed
biological plans use this feature contract. Reused components require adaptation
and new QA; these tools do not directly update the open Illustrator document.

## Review and gate

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\redraw_audit.py" --svg master.svg --plan drawing-plan.json --artifacts connector-checks --report redraw-audit.json --cache-dir render-cache
& $taskPy -X utf8 "$taskSkill\scripts\render_compare.py" --source reference.png --svg master.svg --regions regions.json --report comparison.json --preview preview.png --region-previews qa-regions --cache-dir render-cache
& $taskPy -X utf8 "$taskSkill\scripts\quality_gate.py" --svg master.svg --drawing-plan drawing-plan.json --comparison comparison.json --review visual-review.json --output quality-gate.json --cache-dir render-cache
```

Critical regions have id, source bbox_px, critical:true and preselected max_mae /
min_edge_f1 / min_low_contrast_edge_f1 limits. Do not loosen failures. Inspect
preview, enlarged contours/interiors, every isolated/hidden arrow and old
footprints. Metrics cannot prove ownership or anatomical fidelity.

visual-review.json binds svg_sha256 and has evidence-based pass statuses for
text, connections, critical_objects, background, single_figure, object_editability,
vector_construction, connector_isolation and shape_editability. Review every
critical region and set unresolved_issues:[] only after resolving them. Evidence
must say what was actually inspected. The gate separately audits the drawing
plan and route geometry, so a manually marked pass cannot approve a color mesh.

## Drawing and recovery

```powershell
& "$taskSkill\scripts\native_svg_import.ps1" -InputSvg master.svg -QaReport quality-gate.json -WorkDir native -OutputAi result.ai -OutputPng result.png -ObjectMode symbol -LiveDraw -DelayMs 250
& "$taskSkill\scripts\verify_native_editability.ps1" -NativeWorkDir native -OutputReport native-editability.json
& "$taskSkill\scripts\export_native_figure.ps1" -NativeWorkDir native -QaReport quality-gate.json -OutputPng final.png -OutputAi source-size.ai
& $taskPy -X utf8 "$taskSkill\scripts\verify_native_export.py" --source reference.png --export final.png --regions regions.json --report native-comparison.json
```

Use -DryRun for preparation without Illustrator; -SmokeTest validates a small
reviewed sample using a temporary document. A skills-only update never runs live
calls. Capture the existing target and preserve prior art. Each step copies a
complete group; no per-path batch playback. Source measurements/text creation
require that document active. Export is anchored to the background canvas.

Native symbol mode verifies repeated ungroup and movement of every owner, and
inspects editable text and gradient fills/strokes in disposable expanded copies. Symbol
instances contain internal paths but require deliberate entry into the definition
to modify them. Never substitute a screenshot or flatten the final instances.
Symbol definition names must fit Illustrator's 63-character limit. The bridge
keeps a readable biological name prefix with a compact hash/index suffix. Symbol
bounds include painted strokes; conversion preserves visible bounds to prevent
position shifts. Native inspection counts a compound path as one authored part,
while testing movement of all its subpaths and recursively counting live text.
prepare_native_svg.py converts rectangle primitives to explicit cubic outlines
before native scaling, so Illustrator's live-corner preference cannot alter the
cell membrane. Export copies expand symbols before rescaling vectors: rescaling
and then breaking links can leave hairline strokes. The user's instances remain
protected. Compare the actual canvas export and final export at enlarged scale;
a passing global pixel score cannot excuse changed corners or lost line width.
Inspect native output, fonts, all object movement checks and intact old
footprints. A successful SVG preview does not prove native output. Preserve user
art and save a new AI path. Deliver one diagram; contact sheets are internal QA.

The bridge records phase/status and rejects duplicate attempts. Inspect a failed
job before retrying; never queue behind a hung script. Use a fresh WorkDir after
SVG/runtime/placement changes, and fix only this job. The public skill is self-contained; native text preparation uses its bundled
svg_text_geometry.py. Legacy external-skill diagnostic playback is excluded.

Validate skills-only changes with scripts/tests/test_skill.py and the redraw
regression suite. These use synthetic references/mocks, no user images, APIs or
Illustrator connection. Test success does not establish visual parity with a
remote model.

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\tests\test_skill.py" --report baseline-tests.json
& $taskPy -X utf8 "$taskSkill\scripts\tests\test_redraw.py" --report redraw-tests.json
& $taskPy -X utf8 "$taskSkill\scripts\tests\test_native_paint.py"
& $taskPy -X utf8 "$taskSkill\scripts\tests\test_detail_refinement.py" --report detail-tests.json
& $taskPy -X utf8 "$taskSkill\scripts\tests\test_speed.py" --report speed-tests.json
```

The detail suite covers pinned corners/smooth joins, missed concavities, foreign
or missing features, native paint preservation, grouped typography, stale
patches and unchanged siblings. Its native gradient inspector uses a mock and
contacts no application. Before installing changes, archive the current source
with hashes, preserve local dependency/runtime settings, and validate the staged
skill. Runtime dependencies are separate from the source-version archive.
