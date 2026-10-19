# Release checks — 1.1.0

- Validated the installed and repository skill frontmatter with the Codex
  skill-creator validator.
- Passed all 173 synthetic Python regression cases on Windows, including the
  PowerShell connection backend and Node.js native-bridge mocks, with no
  failures, errors or skips.
- Passed the six standalone export-owner/collision scenarios and symbol-name
  JSX mock; parsed all six bundled PowerShell sources without errors.
- Keep the existing source-specific visual, native editing and actual-export
  gates unchanged. This skill-only update does not connect to Illustrator and
  does not claim new live or cross-version Illustrator validation.
- Publish only portable source, references and tests. Exclude local configuration,
  dependency downloads, cache files, fonts, user references and generated artwork.

The 1.0.0 clean-install and dependency-isolation checks below remain historical
evidence; dependency pins are unchanged. Public CI additionally runs the new
font-independent font/session/review regressions.

## Release checks — 1.0.0

- Skill frontmatter validated with the Codex skill-creator validator.
- Full skill directory copied through the Codex skill-installer copy routine
  into an isolated destination, without a developer configuration or packages.
- All six pinned dependencies freshly installed from PyPI into that skill.
  The runtime audit loaded every module from that skill's private .deps only.
- 164 synthetic Python regression cases passed on Windows/Python 3.12.
- Native export-owner/collision JSX mock checks and symbol name checks passed.
- The independent text geometry parser preserved all canonical live-text
  records in a private compatibility comparison against the previous version.
- PowerShell sources parsed successfully. This release's validation made no
  live Illustrator calls and does not claim new cross-version native testing.

The existing Illustrator drawing, whole-object editing and actual-export checks
remain mandatory for each delivered figure. Synthetic tests are not a visual
quality guarantee for an unseen reference. Public CI covers font-independent
synthetic vector checks; full typography tests require local Arial/Arial Narrow.
