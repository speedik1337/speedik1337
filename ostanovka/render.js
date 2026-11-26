const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({viewport:{width:1588,height:1123}});
  const fs=require('fs'); const svg=fs.readFileSync(process.argv[2],'utf8');
  await p.setContent(`<html><head><style>@page{size:420mm 297mm;margin:0}html,body{margin:0}svg{display:block}</style></head><body>${svg}</body></html>`);
  await p.pdf({path:'ostanovka_A3.pdf', width:'420mm', height:'297mm', printBackground:true});
  await p.setViewportSize({width:1588,height:1123});
  await p.evaluate(()=>{const s=document.querySelector('svg');s.setAttribute('width','1588');s.setAttribute('height','1123');});
  await p.screenshot({path:process.argv[3]||'preview.png'});
  await b.close();
})();
