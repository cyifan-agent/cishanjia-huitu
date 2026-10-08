# Faster recreation with the same quality requirements

Reduce repeated preparation/rendering and artificial pauses. Do not lower image
resolution, simplify anatomy, embed source screenshots, flatten editing objects,
loosen thresholds or skip final appearance/native checks to gain speed.

## Prepare and revise once per meaningful change

Inspect source layout and enlarged ambiguous details together, then freeze the
inventory, coordinates, feature ownership and typography groups before assembly.
For repeated motifs that actually match in this reference, author one complete
source-specific component/helper and instantiate it with unique part/owner IDs.
Adapt each differing contour, damage state, internal structure and pose. Reused
native symbol definitions must not couple separately editable objects.

Fit fonts after the layout is stable. A change to an organelle outline does not
require refitting unrelated text. If a text style group changes, preserve the
group's common family and inspect every affected run. Use scene_patch.py for
complete owner revisions; keep each old master intact. Work from the object-level
defect list and repair actual failures rather than rebuilding the whole figure.

Freeze one source/master/plan revision while checking it. Batch independent
read-only local checks when tool execution allows it; final gating follows their
completion and actual visual inspection. Never overlap Illustrator bridge calls
or enqueue retries behind a hung native script. Skill regression suites are for
tool changes, not something to rerun during every ordinary figure recreation.

## Reuse exact diagnostic rendering

Pass the same project-local cache directory to every review command:

```powershell
& $taskPy -X utf8 "$taskSkill\scripts\redraw_audit.py" --svg master.svg --plan drawing-plan.json --artifacts connector-checks --report redraw-audit.json --cache-dir render-cache
& $taskPy -X utf8 "$taskSkill\scripts\render_compare.py" --source reference.png --svg master.svg --regions regions.json --report comparison.json --preview preview.png --region-previews qa-regions --cache-dir render-cache
& $taskPy -X utf8 "$taskSkill\scripts\quality_gate.py" --svg master.svg --drawing-plan drawing-plan.json --comparison comparison.json --review visual-review.json --output quality-gate.json --cache-dir render-cache
```

Standalone feature_audit.py also accepts --cache-dir. These flags are optional
for compatibility; the default skill workflow supplies them. Cache files contain
only lossless diagnostic PNGs and their hashes. They are not artwork and must
never be inserted into Illustrator as substitutes for vector owners.

render_cache.py keys entries by exact isolated/full SVG contents, explicit output
dimensions, selected font-file contents, renderer/native binary and cache-tool
identity. This includes paths, transforms, text, stroke width, colors, opacity and
gradient stops. Identical temporary font aliases preserve original timestamps so
the normalized font bytes remain stable. Font contents are re-read for identity;
filenames and modification times alone cannot approve stale text.

Unchanged owners can reuse their exact feature/connector pixels during a local
repair. A changed shape or paint is rendered again. Plan ownership, required
features, counts, measured landmarks, routes and thresholds are re-evaluated on
every audit, including when PNGs are cache hits. A changed reference or region
policy still produces new comparison metrics. Cached PNGs never reuse a PASS
report or a visual/native approval. Final QA retains current master/plan hashes;
stale visual reviews fail as before.

Memory use is bounded. A corrupt/incomplete or unwritable disk cache falls back
to normal rendering. Cache reports expose requests, actual renderer calls, hits
and cache errors. Inspect a failing check and fix its object; never clear errors
or relax limits to make a faster result appear correct.

## Faster visible Illustrator drawing

native_svg_import.ps1 retains complete-object commits and one app.redraw per
object. Its deliberate pause defaults to 250 ms instead of 1200 ms. -DelayMs
remains configurable when the user wants to watch more slowly. Geometry, paint,
live text, protection from ungroup and placement are unchanged by this parameter.
Do not skip redraw or collapse the whole figure into an image to accelerate it.

The final actual Illustrator export, every-owner movement check, five repeated
ungroup cycles and enlarged visual review remain required. This skill update
does not contact Illustrator to benchmark a user's open drawing.

## Measure the limited claim

scripts/tests/test_speed.py checks identical PNG bytes/pixels, font/gradient/shape
invalidation, corrupted-cache fallback, unchanged logical failures and fresh
review requirements. It also compares fast/slow native preparation in -DryRun.
Its synthetic repeat-audit benchmark excludes manual reconstruction, human review
and Illustrator. Report that scope; do not turn a cache timing or a reduction in
deliberate pauses into a promised speedup for an entire complex figure.
