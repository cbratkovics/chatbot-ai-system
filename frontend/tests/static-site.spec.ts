import { test, expect } from '@playwright/test';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';
import { execFileSync } from 'node:child_process';

const ORIGIN = 'http://127.0.0.1:4173';

// Installed before creating/navigating a page. No successful fake API responses.
test.beforeEach(async ({ context }) => {
  await context.route('**/*', async (route) => {
    if (new URL(route.request().url()).origin !== ORIGIN) await route.abort('blockedbyclient');
    else await route.continue();
  });
  await context.routeWebSocket(/.*/, (socket) => socket.close());
  await context.addInitScript(() => {
    const calls: string[] = [];
    Object.defineProperty(window, '__networkMechanisms', { value: calls });
    const originalFetch = window.fetch;
    window.fetch = (...args) => {
      calls.push(`fetch:${String(args[0])}`);
      return originalFetch(...args);
    };
    const open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method: string, url: string | URL, async: boolean = true, username?: string | null, password?: string | null) {
      calls.push(`xhr:${String(url)}`);
      return open.call(this, method, url, async, username, password);
    };
    const beacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = (...args) => {
      calls.push(`beacon:${String(args[0])}`);
      return beacon(...args);
    };
    for (const name of ['WebSocket', 'EventSource', 'Worker', 'SharedWorker'] as const) {
      const Original = window[name];
      if (!Original) continue;
      Object.defineProperty(window, name, {
        value: new Proxy(Original, {
          construct(_target, args) {
            calls.push(`${name}:${String(args[0])}`);
            throw new Error(`Unexpected ${name} in static site`);
          },
        }),
      });
    }
  });
});

test('overview, recorded evals, navigation and refresh need only static assets', async ({ page, context }, info) => {
  const requests: string[] = [];
  const errors: string[] = [];
  context.on('request', (request) => requests.push(request.url()));
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  const collectCalls = () => page.evaluate(() => (window as unknown as { __networkMechanisms: string[] }).__networkMechanisms);
  const calls: string[] = [];
  await page.goto('/?live=1&mode=live');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('An LLM gateway you can inspect.');
  await expect(page.getByText('Live model generation is not hosted.', { exact: false }).first()).toBeVisible();
  await expect(page.getByRole('textbox')).toHaveCount(0);
  await expect(page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('overview.png'), fullPage: true });
  calls.push(...await collectCalls());
  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('An LLM gateway you can inspect.');
  calls.push(...await collectCalls());
  await page.getByRole('link', { name: 'Explore recorded evaluations' }).click();
  await expect(page).toHaveURL(/\/evals\/$/);
  await expect(page.getByRole('heading', { name: 'Recorded system evaluations' })).toBeVisible();
  calls.push(...await collectCalls());
  await page.reload();
  await expect(page.getByText('source: committed artifact')).toBeVisible();
  await expect(page.getByText('2026-09-09 10:57:49 UTC', { exact: true })).toBeVisible();
  await expect(page.getByText('9ccfc09 (dirty tree / uncommitted changes)', { exact: true })).toBeVisible();
  await expect(page.getByText('187 in 149.4 s, 0 failed', { exact: true })).toBeVisible();
  await expect(page.getByText('http://localhost:8000', { exact: true })).toBeVisible();
  await expect(page.getByText('Historical estimated cost', { exact: true })).toBeVisible();
  await expect(page.getByText('$0.003755 spent · $0.002419 avoided', { exact: true })).toBeVisible();
  await expect(page.getByText('23 false positive', { exact: true })).toBeVisible();
  await expect(page.getByText(/checking the live|backend did not answer|Connecting|Waking up/)).toHaveCount(0);
  await page.getByRole('button', { name: 'Why precision matters' }).focus();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('tooltip')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByText('Full sweep table', { exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('details').filter({ has: page.getByText('Full sweep table', { exact: true }) })).toHaveAttribute('open', '');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('evals.png'), fullPage: true });
  calls.push(...await collectCalls());
  // Direct /evals (without trailing slash) also resolves on a directory-style static host.
  await page.goto('/evals');
  await expect(page.getByRole('heading', { name: 'Recorded system evaluations' })).toBeVisible();
  calls.push(...await collectCalls());
  await page.goto('/');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main')).toBeFocused();
  calls.push(...await collectCalls());
  expect(requests.filter((url) => new URL(url).origin !== ORIGIN)).toEqual([]);
  expect(calls.filter((call) => /^(beacon|WebSocket|EventSource|Worker|SharedWorker):/.test(call) || /https?:\/\/(?!127\.0\.0\.1:4173)/.test(call) || /\/api\//.test(call))).toEqual([]);
  expect(errors).toEqual([]);
  const audit = JSON.stringify({ requests, mechanisms: calls, errors }, null, 2);
  writeFileSync(info.outputPath('request-audit.json'), audit);
  await info.attach('request-audit', { body: audit, contentType: 'application/json' });
});

test('static output and public build reject backend activation', async ({ request }) => {
  const response = await request.get('/evals/');
  expect(response.headers()['content-security-policy']).toContain("connect-src 'self'");
  // Vercel's Next adapter reads Next manifests before detecting the static export.
  const hostConfig = JSON.parse(readFileSync('vercel.json', 'utf8'));
  expect(hostConfig.framework).toBe('nextjs');
  expect(hostConfig.outputDirectory).toBe('.next');
  expect(JSON.parse(readFileSync('.next/routes-manifest.json', 'utf8')).version).toBe(3);
  const exportDetail = JSON.parse(readFileSync('.next/export-detail.json', 'utf8'));
  expect(exportDetail.success).toBe(true);
  expect(basename(exportDetail.outDirectory)).toBe('out');
  const walk = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? walk(join(dir, entry.name)) : [join(dir, entry.name)]);
  const files = walk('out');
  expect(files.some((file) => /(?:api\/|\.func\/|_worker\.js|server\.js|\.map$)/.test(file))).toBe(false);
  for (const file of files.filter((file) => /\.(html|js|css|txt|json)$/.test(file))) {
    const contents = readFileSync(file, 'utf8');
    expect(contents, file).not.toMatch(/onrender\.com|pinecone\.io|api\.openai\.com|api\.groq\.com|\/chat\/completions|\/chat\/health|sk-(?:proj-|ant-)[A-Za-z0-9_-]{15,}|sk-[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{20,}/);
  }
  expect(() => execFileSync('node', ['-e', "require('./next.config.js')"], { env: { ...process.env, NODE_ENV: 'production', NEXT_PUBLIC_API_URL: 'http://localhost:8000' }, stdio: 'pipe' })).toThrow();
});
