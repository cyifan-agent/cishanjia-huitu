"""Reuse exact diagnostic PNGs; never reuse approval or skip logical checks."""
from pathlib import Path
import hashlib,json,sys,uuid,xml.etree.ElementTree as E
from collections import OrderedDict
from runtime_env import bootstrap
bootstrap()
import resvg_py
from svg_contract import validate

SCHEMA='exact-render-cache-v1'

def sha(payload):return hashlib.sha256(payload).hexdigest()
def engine_identity():
    package=Path(resvg_py.__file__).parent
    # Include the actual renderer code/native binary, not just a package label.
    files=sorted([*package.rglob('*.py'),*package.rglob('*.pyd'),*package.rglob('*.so')])
    return sha(json.dumps({'python':sys.version,'cache_tool':sha(Path(__file__).read_bytes()),'renderer':[(f.relative_to(package).as_posix(),sha(f.read_bytes())) for f in files]},sort_keys=True).encode())

class RenderCache:
    def __init__(self,directory=None,max_memory_bytes=32*1024*1024):
        self.directory=Path(directory) if directory is not None else None
        self.max_memory_bytes=max_memory_bytes;self.memory=OrderedDict();self.memory_bytes=0
        self.engine=engine_identity()
        self.stats={'requests':0,'renderer_calls':0,'memory_hits':0,'disk_hits':0,'cache_errors':0}
    def _remember(self,key,payload):
        if len(payload)>self.max_memory_bytes:return
        if key in self.memory:self.memory_bytes-=len(self.memory.pop(key))
        self.memory[key]=payload;self.memory_bytes+=len(payload)
        while self.memory_bytes>self.max_memory_bytes:
            _,discarded=self.memory.popitem(last=False);self.memory_bytes-=len(discarded)
    def _load(self,key):
        if self.directory is None:return None
        meta_path=self.directory/(key+'.json');png_path=self.directory/(key+'.png')
        if not meta_path.exists() and not png_path.exists():return None
        try:
            meta=json.loads(meta_path.read_text(encoding='utf-8'));payload=png_path.read_bytes()
            if not isinstance(meta,dict):raise ValueError('Invalid cache metadata')
            if meta.get('schema')!=SCHEMA or meta.get('key')!=key or meta.get('png_sha256')!=sha(payload) or not payload.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Cache mismatch')
            return payload
        except (OSError,ValueError,TypeError):self.stats['cache_errors']+=1;return None
    def _save(self,key,payload):
        if self.directory is None:return
        temp=[]
        try:
            self.directory.mkdir(parents=True,exist_ok=True)
            for suffix,content in [('png',payload),('json',json.dumps({'schema':SCHEMA,'key':key,'png_sha256':sha(payload)},sort_keys=True).encode())]:
                pending=self.directory/(key+'.'+uuid.uuid4().hex+'.tmp');temp.append(pending);pending.write_bytes(content);pending.replace(self.directory/(key+'.'+suffix))
        except OSError:self.stats['cache_errors']+=1
        finally:
            for pending in temp:
                if pending.exists():
                    try:pending.unlink()
                    except OSError:pass
    def render(self,svg_string,*,font_files=(),width=None,height=None):
        validate(E.fromstring(svg_string),require_ids=False)
        files=list(font_files)
        options={'skip_system_fonts':True,'font_files':files}
        for name,value in [('width',width),('height',height)]:
            if value is not None:
                if isinstance(value,bool) or not isinstance(value,int) or value<=0:raise ValueError('Positive integer render dimensions required')
                options[name]=value
        # Font contents are re-read, even if their filename/size/timestamp is unchanged.
        key=sha(json.dumps({'schema':SCHEMA,'engine':self.engine,'svg':svg_string,'width':width,'height':height,'fonts':[sha(Path(p).read_bytes()) for p in files]},ensure_ascii=False,sort_keys=True).encode('utf-8'))
        self.stats['requests']+=1
        if key in self.memory:
            payload=self.memory.pop(key);self.memory[key]=payload;self.stats['memory_hits']+=1;return payload
        payload=self._load(key)
        if payload is not None:self.stats['disk_hits']+=1
        else:
            payload=resvg_py.svg_to_bytes(svg_string=svg_string,**options);self.stats['renderer_calls']+=1;self._save(key,payload)
        self._remember(key,payload);return payload

def from_directory(directory):return RenderCache(directory) if directory is not None else None

def render_png(svg_string,*,cache=None,font_files=(),width=None,height=None):
    if cache is not None:return cache.render(svg_string,font_files=font_files,width=width,height=height)
    options={'skip_system_fonts':True,'font_files':list(font_files)}
    if width is not None:options['width']=width
    if height is not None:options['height']=height
    return resvg_py.svg_to_bytes(svg_string=svg_string,**options)
