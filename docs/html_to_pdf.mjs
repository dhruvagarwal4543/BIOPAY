// node docs/html_to_pdf.mjs : FINAL_REPORT.html -> FINAL_REPORT.pdf (needs web/node_modules)
import { chromium } from '../web/node_modules/playwright-core/index.mjs'
import { fileURLToPath } from 'node:url'
const dir = fileURLToPath(new URL('.', import.meta.url))
const b = await chromium.launch(); const p = await b.newPage()
await p.goto('file://' + dir + 'FINAL_REPORT.html'); await p.waitForLoadState('load')
await p.pdf({ path: dir + 'FINAL_REPORT.pdf', format: 'A4', printBackground: true, margin: { top: '18mm', bottom: '18mm', left: '16mm', right: '16mm' },
  displayHeaderFooter: true, headerTemplate: '<span></span>', footerTemplate: '<div style="font-size:9px;width:100%;text-align:center;color:#666">BioPay: simulated payment, no real money. Page <span class="pageNumber"></span> / <span class="totalPages"></span></div>' })
await b.close(); console.log('built pdf')
