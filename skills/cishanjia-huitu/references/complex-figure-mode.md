# Detailed scientific redrawing

Build the complete plan before Illustrator insertion. Measure the actual source;
do not replace a hard motif with a generic symbol. Coherent editable curves must
remain clean at enlarged scale; a source-resolution mosaic is not a redraw.

| Class | Features to measure and redraw |
| --- | --- |
| Heart/rat/syringe/inset | Asymmetry; major vessels/limbs; anatomical colored regions; leaders and border. |
| Compartment | Both boundaries; nucleus arc/gaps; fill; orientation; overlap order. |
| Mitochondrion | Tilted asymmetric body; distinct membranes; source-specific cristae; highlight/shadow contours. |
| DNA | Smooth paired strands; phase; rung spacing; breaks/fragments in the same complete object. |
| Molecular chain | Centers/radii; branches; attachments; coherent highlights; visible bead count. |
| Protein/complex | Accurate silhouette/size; overlap order; useful internal parts; live labels. |
| Arrow/T-bar | Endpoints; centerline controls/tangents; head/cap size; dashes; width/color; independence at crossings. |
| Outcome cell | Irregular contour; blebs; nucleus; vesicles; active/reduced emphasis. |

Work in passes: precise layout and outer contours, internal features, coherent
shading and typography, then local corrections. A layout draft is not a finished
figure. Keep a feature checklist for every complex object until it is complete.

Use [detail-refinement.md](detail-refinement.md) for fixed contour landmarks,
machine-checked primary feature ownership and source bounds, typography groups,
and complete component extraction/local revisions. Measure defining concavities,
not just overall bounding boxes. A cell's internal vesicles and DNA fragments must
be inventoried explicitly. Do not confuse a passing part count with recognition
of those structures.

Tracing one contour may guide a curve refit; inspect and reduce nodes without
erasing defining bends. Never import whole color layers, extract pixel blocks,
or wrap source patches into organelle groups. Many colored rectangles are not
anatomical curves. See true-vector-redraw.md for the final gate.

Draw each connector explicitly. At crossings, its centerline remains its own
path and the other object is layered separately. Do not grow a color-selection
mask around arrows: it can collect nearby molecules, membrane or lettering.
Rebuild hidden contours when movement would reveal a truncated shape.

Compare source scale and enlarged crops. Record each defect by object ID and
geometric correction. Review every arrow in isolation, hidden in the full scene,
and displaced in a copy. All intended arrow parts move; neighbors stay fixed;
background remains at the old footprint. Skills-only updates use synthetic
fixtures and never connect to the user's Illustrator document.

Preserve source relationships in a recreation. Ask when unreadable; scientific
correction requires a separate task. Tests do not establish Cell-LCT parity.
