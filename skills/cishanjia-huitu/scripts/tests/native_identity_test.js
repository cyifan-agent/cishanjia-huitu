const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
function extract(code,name){const start=code.indexOf(' function '+name+'(');assert(start>=0);let brace=code.indexOf('{',start),d=0,end=brace;for(;end<code.length;end++){if(code[end]==='{')d++;else if(code[end]==='}'&&--d===0)break;}return code.slice(start,end+1);}
const dir=process.argv[2];
for(const filename of ['native_svg_import.jsx','export_native_figure.jsx','verify_symbol_editability.ps1','verify_native_editability.ps1']){
 const a={name:'Figure.ai',fullName:{fsName:'C:/A/Figure.ai'},activate(){this.active=true;}},b={name:'Figure.ai',fullName:{fsName:'C:/B/Figure.ai'},activate(){this.active=true;}};
 const docs=[a,b];docs.getByName=()=>a;const c={app:{documents:docs,activeDocument:b},Error};vm.createContext(c);vm.runInContext(extract(fs.readFileSync(path.join(dir,filename),'utf8'),'capturedDocument'),c);
 assert.strictEqual(c.capturedDocument('Figure.ai','C:/B/Figure.ai'),b,filename+' selected wrong same-name document');assert.throws(()=>c.capturedDocument('Figure.ai',''),/ambiguous/i);
 assert.throws(()=>c.capturedDocument('Figure.ai','C:/Missing/Figure.ai'),/missing|not found/i);
}
console.log('NATIVE_IDENTITY_PASS');
