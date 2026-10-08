// Exercise the actual native inspector helper without Illustrator.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[2],'utf8');
const helper=source.match(/function gradientPaints\(node\)\{[^\n]+\}/);
assert(helper,'Missing native paint inspector');
const context={};vm.createContext(context);vm.runInContext(helper[0],context);
const gradient={typename:'GradientColor'},flat={typename:'RGBColor'};
assert.equal(context.gradientPaints({filled:true,fillColor:gradient,stroked:false}),1);
assert.equal(context.gradientPaints({filled:false,stroked:true,strokeColor:gradient}),1);
assert.equal(context.gradientPaints({filled:true,fillColor:gradient,stroked:true,strokeColor:gradient}),2);
assert.equal(context.gradientPaints({filled:true,fillColor:flat,stroked:true,strokeColor:flat}),0);
assert.equal(context.gradientPaints({filled:false,fillColor:gradient,stroked:false,strokeColor:gradient}),0);
console.log('PASS: native fill and stroke gradient inspection; no Illustrator connection');
