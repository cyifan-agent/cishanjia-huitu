const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const source = fs.readFileSync(process.argv[2], "utf8");
const start = source.indexOf(" function fontFor(");
const end = source.indexOf(" if(c.preflight)", start);
assert(start >= 0 && end > start);
const fontSource = source.slice(start, end);
const fonts = [
  { name: "Arial-BoldMT", family: "Arial", style: "Bold" },
  { name: "ArialMT", family: "Arial", style: "Regular" },
  { name: "Arial-ItalicMT", family: "Arial", style: "Italic" },
  { name: "Arial-BoldItalicMT", family: "Arial", style: "Bold Italic" },
  { name: "ArialNarrow", family: "Arial", style: "Narrow" },
  { name: "ArialNarrow-Bold", family: "Arial", style: "Narrow Bold" },
];
fonts.getByName = function(name) {
  // Reproduce problematic family lookup returning the first member.
  if (name === "Arial") return fonts[0];
  const found = fonts.find(font => font.name === name);
  if (!found) throw new Error("missing");
  return found;
};
const context = vm.createContext({ app: { textFonts: fonts } });
vm.runInContext("String.prototype.trim=undefined;function actualFamily(font){return String(font.family).toLowerCase().replace(/\\s+/g,' ');}" + fontSource, context);
const resolve = style => context.fontFor({ family: "Arial", weight: "normal", style:"normal", ...style });
assert.strictEqual(resolve({ weight: "normal" }).name, "ArialMT");
assert.strictEqual(resolve({ weight: "700" }).name, "Arial-BoldMT");
assert.strictEqual(resolve({ style: "italic" }).name, "Arial-ItalicMT");
assert.strictEqual(resolve({ weight: "bold", style: "oblique" }).name, "Arial-BoldItalicMT");
assert.throws(()=>context.fontFor({family:"Absent",weight:"normal",style:"normal"}), /unavailable/);
assert.strictEqual(context.fontFor({family:"Arial Narrow",weight:"bold",style:"normal"}).name,"ArialNarrow-Bold");
assert.strictEqual(context.fontFor({family:"Arial Narrow",weight:"normal",style:"normal"}).name,"ArialNarrow");
const boldOnly = [fonts[0]];
boldOnly.getByName = () => boldOnly[0];
context.app.textFonts = boldOnly;
assert.throws(()=>resolve({weight:"normal"}), /unavailable/);
console.log("FONT_TEST_PASS 8");
