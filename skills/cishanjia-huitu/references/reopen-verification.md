# Verify the saved AI after reopening

Saving, exporting, or passing the in-memory editability test does not verify that
the delivered AI opens with the same appearance and editable contents. Run this
check for every final AI, including each figure in a series. This procedure is a
delivery step; a skills-only maintenance request must not open user artwork.

## Reopen the actual saved bytes

1. Finish saving the intended AI and wait for the save to complete. Record its
   absolute path, SHA-256, Illustrator version, source dimensions, and a baseline
   actual Illustrator export. Preserve any user's unsaved work and existing tabs.
2. Make a byte-for-byte AI copy in a project-local verification directory. Check
   that its hash matches the final AI. Open that copy from disk, close only that
   temporary document without saving, then reopen the same disk copy. Do not
   duplicate an in-memory document or reopen an SVG as a substitute. This tests
   the delivered bytes without closing the user's document or application.
3. Observe opening with user interaction enabled. Use an available UI interface
   to inspect dialogs; a successful COM return or an open performed with
   DONTDISPLAYALERTS cannot establish that no warning appeared. Dispatch opening
   through a bounded, observable operation; do not queue another Illustrator
   command behind a call blocked by a modal dialog. If dialog observation is
   unavailable, record it as unverified and ask the user to report the opening
   prompt instead of asserting a pass.
4. Activate the reopened document before reading artboards, native bounds,
   text, or font properties. Resolve its captured full path, not a foreground tab
   assumption or an ambiguous basename.

## Handle text-layout compatibility prompts

Record the exact warning and the selected action. A prompt saying the text was
created in an older version is not, by itself, proof of the file's actual
creation version or a confirmed application bug.

For the three-button text-layout prompt, choose **Review Changes / 检查更改**
first to retain and compare the original layout. Inspect character positions,
kerning/tracking, line breaks, baselines, mixed CJK/Latin text, Greek letters and
superscripts. Do not automatically choose **Update / 更新**, dismiss the prompt,
disable warnings, or outline the final live text just to suppress it. For other
dialogs, inspect their actual wording before acting; do not reuse a blind click.

If an update is needed, work on a new candidate copy and compare it with the
reviewed baseline. Retain live text and native symbol owners. Save the candidate
using the intended current-version format; derive compatibility from the local
supported options rather than assuming the script's default or hardcoding a
future Illustrator enum. Reopen and recheck the resulting saved bytes. A change
to the delivered AI invalidates its previous file hash and reopening evidence.

Limit corrective save/reopen attempts to two per candidate, then preserve the
evidence and describe the remaining compatibility issue. A recurring prompt
with verified unchanged appearance and editability can be reported as
PASS_WITH_WARNING; it must not be described as warning-free or fully resolved.
Unreviewed dialogs, layout changes, missing text, or lost editability prevent a
successful delivery claim. Do not silently replace the user's final AI with an
updated candidate before that candidate passes its appearance/editability checks.

See Adobe's [text-layout review documentation](https://helpx.adobe.com/illustrator/using/reflow-viewer.html)
for the meaning of the prompt and Review Changes.

## Verify the reopened native document

- Export from the reopened AI at the original source dimensions, anchored to its
  authored background. Compare it with both the approved pre-close native export
  and the source using the same regional thresholds. Inspect the enlarged text
  and critical details; metrics cannot approve a reflow or missing glyph.
- Verify artboard dimensions, object ownership, native symbols/groups, gradients,
  absence of raster/placed substitutions, and every live text run's content and
  font. Document-level text counts alone do not inspect text inside symbols.
- Repeat the existing whole-object movement, fixed-neighbor, and five ungroup
  checks on disposable copies made from the reopened AI. Expand only disposable
  symbol instances to inspect internal vectors and live text. Target a separate
  verification configuration bound to the reopened full path; do not overwrite
  the original native import report or accidentally test the original open tab.
- Close only this job's temporary documents without saving and restore the
  user's active document. Preserve all baseline and reopened exports and reports.

Record `reopen-verification.json` beside the final AI's QA evidence, with:

* `status`: PASS, PASS_WITH_WARNING, UNVERIFIED, or FAIL;
* `final_ai_path`, `final_ai_sha256`, `verification_copy_sha256`,
  `illustrator_version`, and the actual `reopened_document_path`;
* `opened_from_disk`, `closed_and_reopened`, and `dialog_observation`;
* observed `warnings`, selected `actions`, and any remaining limitation;
* paths to baseline/reopened PNGs, source comparison, and reopened editability
  reports, plus evidence for `text_layout`, `live_text`, `objects`, and `canvas`.

Use only observed results. A missing report, an unchecked warning, or a hash from
an earlier candidate cannot support a reopened-file pass. State any unverified
step or recurring warning in the final delivery message. Do not call a mock or
synthetic test an actual Illustrator close/reopen verification.
