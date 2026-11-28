#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {parseArgs} from 'node:util';

const options = Object.fromEntries(
  'project url selector prefix source scene theme scale out-dir'.split(' ').map(k => [k, {type: 'string'}])
);
const {values: args} = parseArgs({options});
if (!args.project || !args.url || !args.prefix || !/^[\w-]+$/.test(args.prefix)) {
  throw Error('用法: export-html-cards.mjs --project <dir> --url <file://|https://> --prefix <id> [--selector ".poster.xhs"]');
}
const selector = args.selector || '.poster.xhs, .social-card, [data-card-aspect="3:4"]';
const scale = Number(args.scale ?? 1);
const project = path.resolve(args.project);
const relDir = args['out-dir'] || path.join('assets/cards', args.prefix);
const outDir = path.join(project, relDir);
fs.mkdirSync(outDir, {recursive: true});

const DEFAULT_PLAYWRIGHT_MODULE = '/opt/homebrew/lib/node_modules/openclaw/node_modules/playwright-core';
const require = createRequire(path.join(project, 'package.json'));
const search = [
  project, process.cwd(), import.meta.dirname,
  ...(process.env.NODE_PATH || '').split(path.delimiter).filter(Boolean),
  path.join(os.homedir(), '.codex/skills/guizang-social-card-skill'),
];
const playwrightModule = process.env.YICE_PLAYWRIGHT_MODULE ||
  (fs.existsSync(DEFAULT_PLAYWRIGHT_MODULE) ? DEFAULT_PLAYWRIGHT_MODULE : null) ||
  require.resolve('playwright-core', {paths: search});
const {chromium} = require(playwrightModule);

function findChromeExecutable() {
  if (process.env.YICE_CHROME_EXECUTABLE && fs.existsSync(process.env.YICE_CHROME_EXECUTABLE)) return process.env.YICE_CHROME_EXECUTABLE;
  const home = os.homedir();
  for (const base of [path.join(home, 'Library/Caches/ms-playwright'), path.join(home, '.cache/ms-playwright'), path.join(home, '.cache/hyperframes/chrome/chrome-headless-shell')]) {
    if (!fs.existsSync(base)) continue;
    for (const d1 of fs.readdirSync(base).sort().reverse()) {
      const p1 = path.join(base, d1);
      if (!fs.statSync(p1).isDirectory()) continue;
      for (const d2 of fs.readdirSync(p1).sort().reverse()) {
        const bin = path.join(p1, d2, 'chrome-headless-shell');
        if (fs.existsSync(bin)) return bin;
      }
    }
  }
  return undefined;
}
const chromeExe = findChromeExecutable();
const browser = await chromium.launch({
  headless: true,
  ...(chromeExe ? {executablePath: chromeExe} : {}),
});
try {
  const page = await browser.newPage({
    viewport: {width: 2400, height: 2200},
    deviceScaleFactor: scale,
    colorScheme: args.theme === 'dark' ? 'dark' : 'light',
  });
  await page.goto(args.url, {waitUntil: 'networkidle', timeout: 30000}).catch(() =>
    page.goto(args.url, {waitUntil: 'domcontentloaded', timeout: 30000})
  );
  await page.evaluate(() => document.fonts ? document.fonts.ready : Promise.resolve());
  await page.waitForTimeout(450);
  const loc = page.locator(selector);
  const count = await loc.count();
  if (!count) throw Error(`页面中未找到匹配卡片选择器 "${selector}"`);
  const exported = [];
  const ledgerPath = path.join(project, 'asset-ledger.jsonl');
  for (let i = 0; i < count; i++) {
    const item = loc.nth(i);
    await item.scrollIntoViewIfNeeded();
    const box = await item.boundingBox();
    if (!box || box.width < 120 || box.height < 120) continue;
    const fileName = `${args.prefix}-${String(i + 1).padStart(2, '0')}.png`;
    const fullPath = path.join(outDir, fileName);
    await item.screenshot({path: fullPath});
    const relPath = path.relative(project, fullPath);
    const entry = {
      id: `${args.prefix}-${String(i + 1).padStart(2, '0')}`,
      kind: 'portrait_card_image',
      sourceType: 'local_card_export',
      url: args.url,
      source: args.source || 'local_demo',
      path: relPath,
      width: Math.round(box.width * scale),
      height: Math.round(box.height * scale),
      aspect: +(box.width / box.height).toFixed(4),
      scene: args.scene || '',
      sha256: createHash('sha256').update(fs.readFileSync(fullPath)).digest('hex'),
      capturedAt: new Date().toISOString(),
      license: 'self_generated',
    };
    fs.appendFileSync(ledgerPath, JSON.stringify(entry) + '\n');
    exported.push(entry);
  }
  console.log(JSON.stringify({ok: true, count: exported.length, items: exported}, null, 2));
} finally {
  await browser.close();
}
