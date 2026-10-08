---
name: cishanjia-huitu
description: Redraw scientific references locally as clean editable vector artwork in Illustrator, with source-specific contours, live text and independently movable arrows and biological objects.
metadata:
  short-description: Local vector redrawing with independent objects
  revision: "2026-10-09-speed-public-1"
---

# cishanjia huitu

This is the portable release of the 2026-10-08-speed-1 workflow, including
subsequent source-arrow and whole-object export fixes. Before first use, read
[installation.md](references/installation.md): resolve this skill directory,
check its local runtime, and initialize missing dependencies once. All drawing
tools are bundled here; do not require another drawing skill or personal paths.

The user wants drawing, not an image placed into Illustrator. Use the reference to measure and inspect; construct the deliverable from authored paths, shapes, strokes and live text. Reproduce its layout and detailed biological motifs without redesigning the diagram or simplifying it into generic icons. Default to one complete figure and preserve existing Illustrator artwork. Make no paid image/vector API calls.

Pixel-color meshes, raster crops, clipped screenshots, embedded images and whole-image automatic traces are not finished redraws. A file with no image nodes can still be a pixel mosaic. Do not substitute source-colored rectangles for editable contours, even if its pixel score is excellent. Existing color_mesh.py and automatic-tracing helpers are diagnostic tools only. This preference is established; do not repeatedly offer that fallback.

Read [true-vector-redraw.md](references/true-vector-redraw.md) for source-specific construction and the drawing-plan schema, and [object-grouping.md](references/object-grouping.md) for independent editing. For complex anatomy, grouped font fitting or object-local revisions, also read [detail-refinement.md](references/detail-refinement.md) and [complex-figure-mode.md](references/complex-figure-mode.md). Commands and recovery are in [local-workflow.md](references/local-workflow.md).

Default to the quality-preserving efficiency workflow in [efficient-workflow.md](references/efficient-workflow.md): prepare once, reuse source-matched complete components, pass one project-local --cache-dir to preview/audit/gate commands, and repair only defective owners. Cached exact PNGs are diagnostic evidence only; every logical check and final review still runs. Keep resolution, tolerances, source detail, protected objects and native verification unchanged.

## Prepare before drawing

1. Inspect the source and enlarged critical details. Establish the requested canvas/panel once. Inventory every visible object, text run and connector, including start/end, arrowhead or T-bar, dash pattern and overlap order. If a detail is illegible or ownership ambiguous, ask a focused question while preparing the clear parts; do not invent it.
2. Author the whole drawing plan before touching Illustrator. Measure silhouettes, orientation, control points, internal membranes, strands/rungs, molecule components, colors and label baselines. Each object gets an ID, a feature checklist and an explicit list of its vector parts. Each arrow gets its own route and group. Captions remain separate unless the user requests them to move with it.
3. Build source-specific Bezier contours and coherent fills, highlights and shading. compose_scene.py supports explicit paths, primitives, curved arrows and T-bars. Generic organelle/DNA helpers are scaffolds requiring adaptation to this source. Measure defining concavities and extremities, marking sharp corners separately from smooth joins; refine_contour.py pins these anchors during fitting. Local tracing may measure one contour; refit and review it before inclusion, recorded as curve-refit. Do not derive a colored tile grid from the reference.
4. Recreate all text as live text with exact content, style, size, fitted width and baseline. Read the source rather than manufacturing OCR results. manifest_lint.py and fit_text.py support known labels. Set style_group for equivalent source typography and fit a common family per group while retaining each run's weight/style. A cleaned diagnostic image is not a deliverable background.
5. Assemble complete named object groups with object_groups.py as construction owners. DNA owns both broken duplexes and their associated fragments; organelles own silhouettes/interiors/shading; an animal owns its torso, limbs, ears and tail; a dying cell owns nucleus, blebs, vesicles and all decorative interior marks. Connectors own only shafts/dashes/heads/T-bars. Reconstruct hidden contours and keep backgrounds continuous beneath movable objects.
6. For this user's delivery, default to native Illustrator symbol instances (`-ObjectMode symbol`): ordinary ungroup must not dismantle a biological object, even when repeated. One source-specific definition per editing object; double-click its instance to edit internal vector parts and live text. The figure's outer group may be removed. Use ordinary groups only if the user explicitly prefers them. See [object-grouping.md](references/object-grouping.md).
7. Use a single native radial-gradient fill for each elliptical halo (`native_glow` or `native_gradients.py`), instead of dozens of stacked opacity ellipses. Gradient paint belongs to its biological owner or to an independently named halo object. Linear/radial gradients are permitted; raster effects, meshes and color tiles remain forbidden. Refit cell lobes and bleb shapes from this reference, preserving the defining indentations and rims.

## Accept the drawing, not just resemblance

For new detailed biological figures, declare feature_contract:"source-features-v1" in the plan. Give each biological owner required_features and features with explicit owned part IDs, measured critical bounds/landmarks and useful part-count constraints. feature_audit.py detects missing, foreign or double-assigned primary parts and missed source landmarks; redraw_audit.py propagates its failures into the existing gate. This verifies a manually inspected inventory, not automatic anatomical recognition. Legacy plans remain readable; do not use that compatibility to skip the new inventory.

Run redraw_audit.py with the drawing plan. It rejects declared color meshes, dense pixel tiles, missing part declarations and connectors containing text, disallowed shapes or marks outside their planned route. Save and inspect every isolated connector preview. Route checks cannot determine biological meaning or identify every unrelated mark at a crossing.

Run render_compare.py on the single master and critical regions. Inspect contours and interiors at enlarged scale, plus typography, endpoints, inhibition caps and faint dashes. A good global score cannot override missing details, a generic icon or a contaminated arrow. Maintain an object-level defect list and repair it without loosening failed thresholds.

Record evidence for text, connections, critical_objects, background, single_figure, object_editability, vector_construction, connector_isolation and shape_editability. Bind the drawing plan and reviews to the SVG using quality_gate.py. Review every connector in isolation and test movement on a copy: the whole arrow moves, every neighbor stays fixed, and its old footprint has intact background. A parent/count audit alone is insufficient.

## Improve and revise locally

Record defects by object ID: observed source difference, cause, specific geometric/font/ownership correction and new inspection evidence. Correct the object, then re-run affected checks and the bound final gate. When a repeatable tool defect is found, add a synthetic regression before changing the tool; do not add vague promises of higher quality to the skill.

scene_patch.py extracts complete vector components with their live text and paints, and revises explicitly named owners in the construction master. Keep a new revision path; source SVG/plan hashes prevent stale changes. It verifies untouched siblings and isolates replacement paint IDs so neighboring objects cannot be recolored accidentally. Adapt reused contours, topology and labels to the new source. This tool does not replace instances in the user's open Illustrator document. Every revision invalidates old appearance approvals and requires fresh review before native delivery.

## Illustrator delivery

When authorized, use native_svg_import.ps1 with the passing QA report. For visible construction use -LiveDraw: commit complete authored object groups one at a time with a redraw between steps. Prepare and review the composition first. Pixel/point batch playback splits editing units and is not the live drawing route.

Visible playback now defaults to 250 ms of deliberate pause per complete object; increase -DelayMs when the user wants slower observation. Do not add per-path sleeps or repeated screen polling. Illustrator calls remain serial.

Capture source artboard coordinates and group bounds while that document is active. Duplicate each complete group to the target layer, move it into the figure group and convert it to one native symbol without changing bounds. Use meaningful biological names. Cross-document duplication directly to a group can fail. Native collections contain direct children; symbol definitions hide their text from document-level text counts. Inspect an expanded disposable instance to verify live text; never expand the user's instances just for counting. Validate a small synthetic sample after bridge changes. Skills-only updates do not connect to Illustrator.

Inspect the actual Illustrator export. Use verify_native_editability.ps1: symbol mode tests every object, repeats ungroup five times, checks complete translation with unchanged neighbors, and expands only temporary copies to inspect all native vector parts, gradient fills/strokes and live text. Inspect isolated parts and old footprints too. Export at source dimensions anchored to the drawn background. Preserve other artwork and save a new AI. Deliver one preview and explain that double-click enters a biological object; the path entries inside describe editable contours. Do not call an incomplete sketch a successful redraw.

## Scope and limitations

Attach to the existing Illustrator instance; do not launch or close the application. Close only the bridge's temporary documents. A skills-only update must not modify user artwork. Keep references unchanged, credentials out of project files, and uploads/remote APIs out of this skill.

This improves the workflow and checks; it installs no neural vision model and reproduces no proprietary weights. Test success is not visual parity with Cell-LCT. State concrete unresolved differences and continue authorized corrections.

Use scripts/runtime_env.py for local dependencies; preserve runtime.local.json. Keep the source, plan, independent vector parts, master, isolated-connector checks, regional reviews, QA, actual export and AI together. Diagnostic helper output cannot become a finished redraw.
