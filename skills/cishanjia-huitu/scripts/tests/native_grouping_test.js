// Test native ownership routing with mocked group collections; no Illustrator.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[2],'utf8');
function extract(name){
  const start=source.indexOf(' function '+name+'('),brace=source.indexOf('{',start);
  assert(start>=0&&brace>start);
  let depth=0,end=brace;
  for(;end<source.length;end++){if(source[end]==='{')depth++;else if(source[end]==='}'&&--depth===0)break;}
  return source.slice(start,end+1);
}
const context={c:{grouping:'semantic-v1',objects:[]},Error};vm.createContext(context);
vm.runInContext(extract('objectContainers')+'\n'+extract('textContainer'),context);
const root={opacity:100},groups={};
root.groupItems={getByName(name){if(!groups[name])throw Error('missing');return groups[name];},
  add(){const group={parent:root,opacity:100,textFrames:[]};return group;}};
const dna=groups['dna-1']={parent:root,textFrames:[],opacity:100};
context.c.objects=[{id:'dna-1',svg_id:'dna-1',graphic_count:2},{id:'caption',svg_id:'caption',graphic_count:0}];
const containers=context.objectContainers(root);
assert.strictEqual(containers['dna-1'],dna);
assert.strictEqual(context.textContainer({object_id:'dna-1',content:'DNA'},root,containers),dna);
assert.strictEqual(containers.caption.parent,root);
assert.throws(()=>context.textContainer({object_id:'wrong',content:'DNA'},root,containers),/owner/);
context.c.objects=[{id:'missing',svg_id:'missing',graphic_count:3}];
assert.throws(()=>context.objectContainers(root),/group missing/);
groups['dna-1'].parent={};context.c.objects=[{id:'dna-1',svg_id:'dna-1',graphic_count:2}];
assert.throws(()=>context.objectContainers(root),/direct figure child/);
console.log('NATIVE_GROUP_ROUTING_PASS');
