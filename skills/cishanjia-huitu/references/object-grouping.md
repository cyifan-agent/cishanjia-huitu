# Whole-object editing and clean arrow ownership

Construction SVG uses complete named groups, but this user's final AI uses one
native symbol instance per meaningful editing object. Ungrouping the outer figure,
and repeatedly ungrouping the instances, must leave each cell, organelle, DNA,
animal and arrow intact. Double-click opens its definition for internal editing.
Definitions are source-specific and unique per object, so editing one panel does
not silently change the other. Ordinary group delivery is opt-in.

Object ownership is determined by its authored geometry, not hue, proximity,
a crop window or a source mask. A group around a mixed color layer is not an
independent object. Reconstruct any missing hidden shapes rather than extracting
visible source pixels. Background remains complete beneath movable foreground.

A DNA group owns both strands, rungs and break fragments. An organelle owns
silhouette, membranes, cristae, highlights and shadows. A cell owns its contour,
nucleus, blebs and vesicles. Proteins own their live text. A complex can have
internal protein subgroups, with only the outer complex as semantic owner.
An experimental rat includes its tail, all limbs, head, ears, eyes and body
shading. A syringe stays separate. A dying cell includes detached blebs and
interior decorative particles; do not promote its individual circles to separate
editing objects. Both fragmented duplex motifs and their own debris form one
broken-DNA unit when the source treats them as one event.

One halo is one ellipse with native radial-gradient paint, not many concentric
ellipses. Other shading belongs to the object it describes. Native vector paths
are necessary inside definitions; their presence does not justify splitting the
outer biological editing object into anonymous path entries.

**Each arrow owns only its shaft, dashes and arrowhead/T-bar.** Neighboring labels,
membrane fragments and molecules are not members. Captions are separate label
groups by default. At intersections, redraw independent overlapping paths instead
of expanding color-selection masks. This prevents dragging an arrow from carrying
another object, including small fragments invisible at source scale.

## Assemble independent parts

object_groups.py assembles complete top-level nodes without flattening geometry.
Explicitly list all parts; the object list establishes paint order.

```json
{"objects":[
 {"id":"background","name":"背景","kind":"background","member_ids":["background-fill"]},
 {"id":"mito-1","name":"线粒体01","kind":"organelle","member_ids":["mito-body","mito-cristae","mito-shadow","mito-label"]},
 {"id":"dna-1","name":"DNA01","kind":"dna","member_ids":["dna-strands","dna-rungs","dna-fragments"]},
 {"id":"arrow-1","name":"转位箭头01","kind":"connector","member_ids":["arrow-shaft","arrow-head"]}
]}
```

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\object_groups.py" --svg independent-parts.svg --manifest objects.json --output master.svg --report object-groups.json
```

The assembler rejects duplicate/missing/unassigned memberships. It cannot know
that a declared path includes foreign marks. The separate redraw_audit.py checks
the drawing plan, connector geometry and dense tile signatures. Inspect every
isolated arrow, not only a few representative ones.

Semantic-v1 requires direct named g children with matching id/object ID, name and
kind. Every graphic/live text has one owner. Background is an authored vector
group. Pixel meshes with precise masks remain diagnostic; masks do not satisfy
this user's redraw requirement.

## Native acceptance

native_svg_import.ps1 recreates text in owner groups and imports complete groups.
-ObjectMode symbol (default) then converts each owner to one protected instance.
-LiveDraw adds one whole editing object at a time. Batch boundaries must not split editing units.
Preserve source activation during coordinate measurement and text creation.
Duplicate to the target layer before moving into its outer group.

Run verify_native_editability.ps1 after authorized drawing. Symbol mode dispatches
to verify_symbol_editability.ps1. It duplicates only this job to a temporary
document, ungroups the outer figure, repeats ungroup five more times and tests
every object. It inspects expanded disposable instances before/after translation
to verify all vector parts, native gradient paint and text move with the owner,
and that neighbors stay fixed. It closes the test document
and restores the user's original. It does not prove anatomical completeness or
detect all contamination inside a declared group; inspect isolated arrow previews
and old footprints as well. A skills-only update uses tests without Illustrator.
