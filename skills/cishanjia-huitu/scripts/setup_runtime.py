"""Initialize this skill's private dependencies; drawing itself stays offline."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,tempfile
from pathlib import Path
from runtime_env import audit

def configure(root,python,existing=None):
    config=dict(existing or {})
    config.update(python=str(Path(python).resolve()),package_roots=['.deps'])
    fd,name=tempfile.mkstemp(prefix='.runtime-',suffix='.json',dir=root)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(config,f,ensure_ascii=False,indent=2)
        os.replace(name,root/'runtime.local.json')
    finally:
        if os.path.exists(name):os.unlink(name)
    return config

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check',action='store_true',help='Audit only; no downloads or configuration writes')
    p.add_argument('--skip-install',action='store_true',help='Use dependencies already present in this Python environment')
    args=p.parse_args()
    if sys.version_info<(3,11):raise SystemExit('Python 3.11 or newer is required')
    if args.check:
        report=audit();print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['status']=='PASS' else 1
    root=Path(__file__).resolve().parent.parent
    config_path=root/'runtime.local.json'
    existing=json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
    if not args.skip_install:
        subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--target',str(root/'.deps'),'-r',str(root/'requirements.txt')],check=True)
    configure(root,sys.executable,existing)
    # A fresh child avoids mixing modules imported before installing dependencies.
    result=subprocess.run([sys.executable,'-X','utf8',str(root/'scripts/runtime_env.py')])
    return result.returncode

if __name__=='__main__':raise SystemExit(main())
