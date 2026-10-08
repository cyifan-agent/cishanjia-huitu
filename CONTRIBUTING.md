# Development

Install Python 3.12, initialize the skill runtime using its setup_runtime.py,
and run the bundled synthetic suites:

```powershell
python skills/cishanjia-huitu/scripts/tests/test_skill.py
python skills/cishanjia-huitu/scripts/tests/test_redraw.py
python skills/cishanjia-huitu/scripts/tests/test_native_paint.py
python skills/cishanjia-huitu/scripts/tests/test_detail_refinement.py
python skills/cishanjia-huitu/scripts/tests/test_speed.py
python skills/cishanjia-huitu/scripts/tests/test_joined_routes.py
python skills/cishanjia-huitu/scripts/tests/test_source_markers.py
python skills/cishanjia-huitu/scripts/tests/test_portable_runtime.py
node skills/cishanjia-huitu/scripts/tests/test_export_owner.js skills/cishanjia-huitu/scripts/export_native_figure.jsx
node skills/cishanjia-huitu/scripts/tests/symbol_name_test.js skills/cishanjia-huitu/scripts/native_svg_import.jsx
```

These tests use synthetic vectors, temporary files and mocked Illustrator;
they do not upload user images or connect to the application. Node.js is needed
for JSX mocks. Arial and Arial Narrow must be locally available for font tests.
Native bridge changes additionally need a reviewed tiny smoke test in a
temporary Illustrator document on the contributor's Windows installation.

For drawing defects, record the object ID, observed source mismatch, cause,
geometric/typographic correction and renewed inspection evidence. Never loosen
failed quality thresholds, flatten objects or hide a defect behind a global
pixel score. New reusable tool fixes need a behavioral regression.

Do not commit private configs, credentials, downloaded dependencies, fonts,
user artwork or reference images. Keep report output outside the repository.
