#!/usr/bin/env node
/**
 * Universal Deterministic Frame / Segment / Still Renderer for Short Director v0.2.0.
 *
 * Modes:
 *   node render_node.mjs stills <entry_html> <out_dir> <t1,t2,...> <scale> <webgl_backend>
 *   node render_node.mjs segment <entry_html> <out_mp4> <fps> <f_start> <f_end> <scale> <capture_mode> <webgl_backend>
 *   node render_node.mjs hashes <entry_html> <fps> <f_start> <f_end> <scale> <webgl_backend>
 *
 * Supports:
 * - scale=1 -> 1080x1920 preview
 * - scale=2 -> 2160x3840 true native 4K rasterization (Canvas2D vector scale=2, SVG/DOM DPR=2, WebGL pixelRatio=2)
 * - Direct image2pipe streaming to FFmpeg (0 bytes of raw temporary PNG frame files on disk!)
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const __filename = fileURLToPath(import.meta.url);
const kitNodeModules = path.resolve(path.dirname(__filename), '..', 'vendor', 'claude-animation-skills', 'kit', 'node_modules');
const { chromium } = require(path.join(kitNodeModules, 'playwright'));

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
};

function startStaticServer(rootDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
      const safeRel = path.normalize(urlPath).replace(/^(\.\.(\/|\\|$))+/, '');
      const fullPath = path.join(rootDir, safeRel);
      fs.readFile(fullPath, (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end('Not found');
          return;
        }
        res.writeHead(200, { 'Content-Type': MIME_TYPES[path.extname(fullPath).toLowerCase()] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

function buildLaunchArgs(webglBackend) {
  const base = ['--allow-file-access-from-files', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'];
  let effective = webglBackend;
  if (effective === 'metal' && process.platform !== 'darwin') {
    effective = process.platform === 'win32' ? 'd3d11' : 'swiftshader';
  }
  if (effective === 'metal') {
    return [...base, '--use-gl=angle', '--use-angle=metal', '--ignore-gpu-blocklist'];
  }
  if (effective === 'd3d11') {
    return [...base, '--use-gl=angle', '--use-angle=d3d11', '--ignore-gpu-blocklist'];
  }
  if (effective === 'swiftshader') {
    return [...base, '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
  }
  return [...base, '--ignore-gpu-blocklist'];
}

(async () => {
  const mode = process.argv[2];
  const entryHtml = path.resolve(process.argv[3]);
  const rootDir = path.dirname(entryHtml);
  const htmlName = path.basename(entryHtml);

  const scale = Number(
    mode === 'stills' ? process.argv[6] :
    mode === 'segment' ? process.argv[8] :
    mode === 'trace' ? process.argv[5] :
    process.argv[7]
  ) || 1;
  const webglBackend = (
    mode === 'stills' ? process.argv[7] :
    mode === 'segment' ? process.argv[10] :
    mode === 'trace' ? process.argv[6] :
    process.argv[8]
  ) || (process.platform === 'darwin' ? 'metal' : (process.platform === 'win32' ? 'd3d11' : 'swiftshader'));

  const chromeExe = process.env.PLAYWRIGHT_CHROME_PATH || process.env.CHROME || undefined;
  const { server, port } = await startStaticServer(rootDir);

  let browser;
  const pageErrors = [];
  try {
    browser = await chromium.launch({
      ...(chromeExe ? { executablePath: chromeExe } : {}),
      args: buildLaunchArgs(webglBackend),
    });
    const context = await browser.newContext({
      viewport: { width: 1080, height: 1920 },
      deviceScaleFactor: scale,
    });
    const page = await context.newPage();
    page.on('pageerror', err => {
      pageErrors.push(err.message || String(err));
      console.error('[pageerror]', err.message || String(err));
    });

    await page.goto(`http://127.0.0.1:${port}/${htmlName}?render=1&scale=${scale}`, { waitUntil: 'load' });
    await page.waitForFunction(() => window.SHORT_DIRECTOR_READY && window.renderAtTime, { timeout: 25000 });
    await page.evaluate(() => window.SHORT_DIRECTOR_READY);

    if (pageErrors.length > 0) {
      throw new Error(`Page runtime error during init: ${pageErrors.join('; ')}`);
    }

    if (mode === 'stills') {
      const outDir = path.resolve(process.argv[4]);
      const times = process.argv[5].split(',').filter(Boolean).map(Number);
      fs.mkdirSync(outDir, { recursive: true });
      const results = [];
      for (const t of times) {
        await page.evaluate(ts => window.renderAtTime(ts), t);
        const outPath = path.join(outDir, `still_${t.toFixed(3)}.png`);
        const buf = await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: 1080, height: 1920 } });
        fs.writeFileSync(outPath, buf);
        results.push({ time: t, path: outPath, bytes: buf.length });
      }
      console.log(JSON.stringify({ ok: true, stills: results }));
    } else if (mode === 'segment') {
      const outMp4 = path.resolve(process.argv[4]);
      const fps = Number(process.argv[5]);
      const fStart = Number(process.argv[6]);
      const fEnd = Number(process.argv[7]);
      const captureMode = process.argv[9] || 'page_jpeg';

      fs.mkdirSync(path.dirname(outMp4), { recursive: true });
      const tmpMp4 = outMp4 + '.part.mp4';
      const ffArgs = [
        '-y', '-v', 'error',
        '-f', 'image2pipe',
        '-framerate', String(fps),
        '-c:v', 'mjpeg',
        '-i', '-',
        '-vf', 'scale=in_range=pc:out_range=tv,format=yuv420p',
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-crf', scale >= 2 ? '16' : '16',
        '-pix_fmt', 'yuv420p',
        '-color_range', 'tv',
        '-r', String(fps),
        tmpMp4,
      ];
      const ff = spawn('ffmpeg', ffArgs, { stdio: ['pipe', 'inherit', 'inherit'] });

      for (let f = fStart; f < fEnd; f++) {
        const t = f / fps;
        let jpgBuf;
        if (captureMode === 'canvas_jpeg') {
          const dataUrl = await page.evaluate(ts => {
            window.renderAtTime(ts);
            return window.grabCanvasDataURL('image/jpeg', 0.96);
          }, t);
          jpgBuf = Buffer.from(dataUrl.split(',')[1], 'base64');
        } else {
          await page.evaluate(ts => window.renderAtTime(ts), t);
          jpgBuf = await page.screenshot({ type: 'jpeg', quality: 96, clip: { x: 0, y: 0, width: 1080, height: 1920 } });
        }
        if (!ff.stdin.write(jpgBuf)) {
          await new Promise(r => ff.stdin.once('drain', r));
        }
      }
      ff.stdin.end();
      const exitCode = await new Promise(r => ff.on('close', r));
      if (exitCode !== 0 || pageErrors.length > 0) {
        throw new Error(`Segment encode failed (ffmpeg=${exitCode}, pageErrors=${pageErrors.length})`);
      }
      fs.renameSync(tmpMp4, outMp4);
      console.log(JSON.stringify({ ok: true, out: outMp4, frames: fEnd - fStart, scale }));
    } else if (mode === 'hashes') {
      const fps = Number(process.argv[4]);
      const fStart = Number(process.argv[5]);
      const fEnd = Number(process.argv[6]);
      const hashes = [];
      for (let f = fStart; f < fEnd; f++) {
        const t = f / fps;
        await page.evaluate(ts => window.renderAtTime(ts), t);
        const buf = await page.screenshot({ type: 'png', clip: { x: 0, y: 0, width: 1080, height: 1920 } });
        const sha = crypto.createHash('sha256').update(buf).digest('hex');
        hashes.push({ frame: f, time: Number(t.toFixed(4)), sha256: sha, bytes: buf.length });
      }
      console.log(JSON.stringify({ ok: true, hashes }));
    } else if (mode === 'trace') {
      const times = (process.argv[4] || '').split(',').filter(Boolean).map(Number);
      const traces = [];
      for (const t of times) {
        const rec = await page.evaluate(ts => {
          const shotIdx = window.renderAtTime(ts);
          return {
            time: Number(ts.toFixed(4)),
            shot_index: shotIdx,
            telemetry: window.__LAST_RENDER_TELEMETRY__ || null,
          };
        }, t);
        traces.push(rec);
      }
      console.log(JSON.stringify({ ok: true, traces }));
    } else {
      throw new Error(`Unknown render_node.mjs mode: ${mode}`);
    }
  } finally {
    if (browser) await browser.close();
    server.close();
  }
})().catch(err => {
  console.error(err);
  process.exit(1);
});
