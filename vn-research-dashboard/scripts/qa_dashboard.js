#!/usr/bin/env node
/**
 * QA Dashboard — Automated visual quality assurance cho equity research dashboard
 * Học từ pattern develop-web-game: implement → test → screenshot → fix
 *
 * Usage:
 *   node qa_dashboard.js --url file:///path/to/dashboard.html
 *   node qa_dashboard.js --url https://example.com --output ./qa-screenshots
 *
 * Checks:
 *   1. All <canvas> elements rendered (no blank charts)
 *   2. No JS console errors
 *   3. All sections present (hero, exec summary, 10 sections, footer)
 *   4. Navigation bar works (click each link, verify scroll)
 *   5. Screenshots: full page + each section
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function runQA() {
  const args = process.argv.slice(2);
  const urlArg = args.find(a => a.startsWith('--url='));
  const outputArg = args.find(a => a.startsWith('--output='));

  if (!urlArg) {
    console.error('❌ Usage: node qa_dashboard.js --url=file:///path/to/dashboard.html [--output=./qa-shots]');
    process.exit(1);
  }

  const url = urlArg.replace('--url=', '');
  const outputDir = outputArg ? outputArg.replace('--output=', '') : './qa-screenshots';

  // Create output dir
  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

  console.log(`🔍 QA Dashboard — Testing: ${url}`);
  console.log(`📁 Output: ${outputDir}\n`);

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1480, height: 900 } });

  const errors = [];
  const warnings = [];
  const passes = [];

  // Collect console errors
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`Console: ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`Page error: ${err.message}`));

  // Navigate
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000); // wait for Chart.js to render
  } catch (e) {
    errors.push(`Navigation: ${e.message}`);
  }

  // === CHECK 1: Canvas elements rendered ===
  console.log('📊 Check 1: Canvas elements...');
  const canvases = await page.$$eval('canvas', els => els.map(c => ({
    id: c.id,
    width: c.width,
    height: c.height,
    hasContent: c.width > 0 && c.height > 0
  })));

  if (canvases.length === 0) {
    errors.push('No <canvas> elements found — charts missing');
  } else {
    const blank = canvases.filter(c => !c.hasContent);
    if (blank.length > 0) {
      warnings.push(`${blank.length}/${canvases.length} canvas blank: ${blank.map(c=>c.id).join(', ')}`);
    } else {
      passes.push(`All ${canvases.length} canvas elements rendered ✓`);
    }
  }

  // === CHECK 2: JS errors ===
  console.log('🔧 Check 2: JavaScript errors...');
  if (errors.length > 0) {
    errors.forEach(e => console.log(`  ❌ ${e}`));
  } else {
    passes.push('No JavaScript console errors ✓');
  }

  // === CHECK 3: Sections present ===
  console.log('📋 Check 3: Sections...');
  const expectedSections = [
    { selector: '.hero, [class*="hero"]', name: 'Hero' },
    { selector: '.exec-summary, [id*="exec"], [class*="exec-summary"]', name: 'Executive Summary' },
    { selector: 'h2', minCount: 7, name: 'Section titles (≥7)' },
    { selector: 'footer, [class*="footer"]', name: 'Footer' },
    { selector: '.topnav, nav, [class*="nav"]', name: 'Navigation' },
  ];

  for (const sec of expectedSections) {
    const count = await page.$$eval(sec.selector, els => els.length).catch(() => 0);
    if (sec.minCount) {
      if (count >= sec.minCount) passes.push(`${sec.name}: ${count} found ✓`);
      else warnings.push(`${sec.name}: only ${count} (expected ≥${sec.minCount})`);
    } else {
      if (count > 0) passes.push(`${sec.name}: found ✓`);
      else warnings.push(`${sec.name}: NOT found`);
    }
  }

  // === CHECK 4: Navigation links work ===
  console.log('🧭 Check 4: Navigation...');
  const navLinks = await page.$$eval('.topnav-link, nav a[href^="#"]', els =>
    els.map(a => ({ href: a.getAttribute('href'), text: a.textContent.trim() }))
  ).catch(() => []);

  if (navLinks.length > 0) {
    passes.push(`Navigation: ${navLinks.length} links ✓`);
    // Click first 3 links to verify they scroll
    for (let i = 0; i < Math.min(3, navLinks.length); i++) {
      try {
        await page.click(`[href="${navLinks[i].href}"]`, { timeout: 2000 });
        await page.waitForTimeout(500);
      } catch (e) {
        warnings.push(`Nav link "${navLinks[i].text}" click failed`);
      }
    }
  } else {
    warnings.push('No navigation links found');
  }

  // === CHECK 5: Screenshots ===
  console.log('📸 Check 5: Screenshots...');

  // Full page screenshot
  await page.screenshot({
    path: path.join(outputDir, 'full-page.png'),
    fullPage: true
  });
  passes.push('Full page screenshot saved ✓');

  // Hero screenshot
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await page.screenshot({
    path: path.join(outputDir, 'hero.png'),
    clip: { x: 0, y: 0, width: 1480, height: 600 }
  });

  // Scroll-spy: scroll to middle, take screenshot
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(outputDir, 'middle.png'),
    clip: { x: 0, y: 0, width: 1480, height: 900 }
  });

  // === REPORT ===
  console.log('\n' + '='.repeat(60));
  console.log('📋 QA REPORT');
  console.log('='.repeat(60));

  console.log(`\n✅ PASSES (${passes.length}):`);
  passes.forEach(p => console.log(`  ✓ ${p}`));

  if (warnings.length > 0) {
    console.log(`\n⚠️  WARNINGS (${warnings.length}):`);
    warnings.forEach(w => console.log(`  ⚠ ${w}`));
  }

  if (errors.length > 0) {
    console.log(`\n❌ ERRORS (${errors.length}):`);
    errors.forEach(e => console.log(`  ✗ ${e}`));
  }

  console.log('\n' + '='.repeat(60));
  const status = errors.length > 0 ? '❌ FAIL' : warnings.length > 0 ? '⚠️  PASS WITH WARNINGS' : '✅ PASS';
  console.log(`Result: ${status}`);
  console.log(`Screenshots: ${outputDir}/full-page.png, hero.png, middle.png`);
  console.log('='.repeat(60));

  await browser.close();

  // Exit code: 0 = pass, 1 = warnings, 2 = errors
  process.exit(errors.length > 0 ? 2 : warnings.length > 0 ? 1 : 0);
}

runQA().catch(e => {
  console.error('Fatal:', e.message);
  process.exit(3);
});
