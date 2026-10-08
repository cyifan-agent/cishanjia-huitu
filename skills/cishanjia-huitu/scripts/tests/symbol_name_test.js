const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[2],'utf8');
const start=source.indexOf(' function definitionName('),brace=source.indexOf('{',start);
let depth=0,end=brace;
for(;end<source.length;end++){if(source[end]==='{')depth++;else if(source[end]==='}'&&--depth===0)break;}
const spec={id:'long-caption',name:'Reduced AIF release/translocation followed by nuclear transport'.repeat(3)};
const context={c:{sha256:'1234567890abcdef',objects:[spec,{id:'next',name:spec.name}]}};
vm.createContext(context);vm.runInContext(source.slice(start,end+1),context);
const first=context.definitionName(spec),next=context.definitionName(context.c.objects[1]);
assert(first.length<=63);assert(next.length<=63);assert.notStrictEqual(first,next);
assert(first.startsWith('Reduced AIF'));console.log('SYMBOL_NAME_LIMIT_PASS');
