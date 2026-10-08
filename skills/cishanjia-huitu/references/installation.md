# Portable installation and first use

Resolve the installed skill directory from this SKILL.md, never from a user's
name, drive letter or a prior session. Every required drawing helper is included
in scripts/. No other drawing skill, private model/API, user reference file or
developer-machine dependency directory is required.

## Runtime setup

Locate a Python 3.11+ interpreter available to this user (3.12 recommended),
including a Codex-provided local runtime when available. Test it before use;
do not assume any vendor runtime's absolute path. From any working directory:

```powershell
# taskSkill and taskPy refer to paths discovered on this user's machine.
& $taskPy -X utf8 "$taskSkill\scripts\setup_runtime.py" --check
# If dependencies are missing, initialize this installed skill once:
& $taskPy -X utf8 "$taskSkill\scripts\setup_runtime.py"
```

Setup installs requirements.txt from PyPI into the skill's private .deps
directory and creates runtime.local.json with this user's interpreter path.
It does not download a neural model, access a reference image or connect to
Illustrator. Do not publish this generated config or dependency directory.
If all packages are already available to the chosen interpreter, --skip-install
records its path without installing. Preserve a working existing configuration.
Package installation is the only network action in this setup tool; drawing
helpers operate locally. Read a setup failure, resolve it, and rerun the check.

## Illustrator

The user opens Illustrator and a target document. The bundled PowerShell helper
attaches to the already-running application through registered Windows COM
identifiers, automatically trying locally registered versions. It never starts
or closes the user's application. Live native calls use Windows PowerShell 5.1
in STA mode (PowerShell 7 forwards those calls automatically). Do not run
multiple Illustrator calls concurrently.

For an unusual installation, the user can set HUITU_ILLUSTRATOR_PROGID or the
private config field illustrator_progid to their locally registered identifier.
Never copy a developer's hardcoded version into another user's config. Original
native drawing behavior was verified on Illustrator 2026/COM 30; other versions
require a small temporary smoke test before a complex delivery. Font resolution
must match fonts available on the user's own machine.

## Skill discovery

Install the entire skills/cishanjia-huitu directory using Codex skill-installer,
not just SKILL.md. Use the installer's configured local destination; do not force
a private developer path. Invoke $cishanjia-huitu after installation. If it does
not appear, reopen Codex. Dependencies are initialized only once, not before
every drawing. Keep results and caches in the current project, outside this skill.
