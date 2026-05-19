from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import Settings
from .logging_utils import configure_logging
from .service import IntroMarkerService


configure_logging()
LOGGER = logging.getLogger("intro_marker.main")
SETTINGS = Settings.load()
SERVICE = IntroMarkerService(SETTINGS)


class RuntimeSettingsPayload(BaseModel):
    dry_run: bool | None = None
    write_ed_as_second_intro_pair: bool | None = None
    include_library_names: str | list[str] | None = None
    min_similarity: float | None = None
    min_support_ratio: float | None = None
    op_position_tolerance_seconds: float | None = None
    ed_tail_tolerance_seconds: float | None = None
    poll_enabled: bool | None = None
    poll_interval_minutes: int | None = None
    nightly_enabled: bool | None = None
    nightly_hour: int | None = None
    nightly_minute: int | None = None
    discovery_min_episodes: int | None = None
    op_search_max_seconds: int | None = None
    ed_search_from_end_seconds: int | None = None


def _page_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Emby Intro Marker</title>
  <style>
    :root { color-scheme: light; --bg:#f3f2ec; --card:#fffdf7; --ink:#1b1b18; --muted:#6d6a60; --line:#d7d0bf; --accent:#0e7a5f; --accent2:#ba5b32; }
    body { margin:0; font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(180deg,#f6f2e8,#ece7db); color:var(--ink); }
    .wrap { max-width:1280px; margin:0 auto; padding:24px; }
    .hero { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:20px; }
    .hero h1 { margin:0 0 8px; font-size:28px; }
    .hero p { margin:0; color:var(--muted); }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:16px 18px; box-shadow:0 8px 24px rgba(0,0,0,.05); }
    .card h2 { margin:0 0 12px; font-size:18px; }
    .kv { display:grid; grid-template-columns:140px 1fr; gap:8px; font-size:14px; }
    .kv div:nth-child(odd) { color:var(--muted); }
    .controls { display:flex; flex-wrap:wrap; gap:10px; margin:12px 0 0; }
    button { border:0; border-radius:999px; padding:10px 16px; font-weight:600; cursor:pointer; }
    .primary { background:var(--accent); color:white; }
    .secondary { background:#ece7db; color:var(--ink); }
    .warn { background:var(--accent2); color:white; }
    label { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:10px 0; font-size:14px; }
    input[type='number'], input[type='text'] { width:180px; padding:8px 10px; border-radius:10px; border:1px solid var(--line); background:white; }
    input[type='checkbox'] { transform:scale(1.2); }
    pre { white-space:pre-wrap; word-break:break-word; background:#f7f4ed; padding:12px; border-radius:12px; border:1px solid var(--line); max-height:500px; overflow:auto; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { border-bottom:1px solid var(--line); padding:8px 6px; text-align:left; vertical-align:top; }
    .muted { color:var(--muted); }
    .ok { color:var(--accent); font-weight:700; }
    .bad { color:#b42318; font-weight:700; }
    .pill { display:inline-block; padding:4px 9px; border-radius:999px; background:#ece7db; margin:2px 6px 2px 0; font-size:12px; }
    .bar { width:100%; height:14px; background:#ece7db; border-radius:999px; overflow:hidden; border:1px solid var(--line); }
    .bar > div { height:100%; background:linear-gradient(90deg,#0e7a5f,#4db69a); width:0%; transition:width .2s ease; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <h1>Emby Intro Marker</h1>
        <p>默认只扫电视剧和动漫库。WebUI 保存后会立即重载扫描范围和后台调度。</p>
      </div>
      <div class="controls">
        <button class="secondary" onclick="refreshAll()">刷新</button>
        <button class="primary" onclick="saveSettings()">保存设置</button>
        <button class="primary" onclick="runSample()">跑 1 个样本季</button>
        <button class="warn" onclick="runTop3()">跑 3 部动漫</button>
        <button class="secondary" onclick="runPoll()">手动轻量轮询</button>
        <button class="secondary" onclick="runBackfill()">手动夜间补扫</button>
      </div>
    </div>

    <div class="grid">
      <section class="card">
        <h2>服务状态</h2>
        <div id="health" class="kv"></div>
      </section>
      <section class="card">
        <h2>调度状态</h2>
        <div id="scheduler" class="kv"></div>
      </section>
      <section class="card">
        <h2>批处理进度</h2>
        <div class="bar" style="margin-bottom:10px;"><div id="batchBar"></div></div>
        <div id="batchMeta" class="kv" style="margin-bottom:10px;"></div>
        <pre id="batchStatus">暂无批处理</pre>
      </section>
    </div>

    <div class="grid" style="margin-top:16px;">
      <section class="card">
        <h2>扫描范围</h2>
        <label><span>库白名单</span><input id="include_library_names" type="text" placeholder="电视剧,动漫"></label>
        <label><span>发现最小集数</span><input id="discovery_min_episodes" type="number" min="1" max="24" step="1"></label>
        <div class="controls">
          <button class="primary" onclick="saveSettings()">保存并立即生效</button>
        </div>
        <div style="margin-top:12px;">
          <div class="muted" style="margin-bottom:6px;">当前可选库</div>
          <div id="libraries"></div>
        </div>
        <div style="margin-top:12px;">
          <div class="muted" style="margin-bottom:6px;">当前实际扫描路径</div>
          <pre id="effectiveRoots">[]</pre>
        </div>
      </section>

      <section class="card">
        <h2>后台任务</h2>
        <label><span>轻量轮询启用</span><input id="poll_enabled" type="checkbox"></label>
        <label><span>轮询间隔(分钟)</span><input id="poll_interval_minutes" type="number" min="5" max="720" step="1"></label>
        <label><span>夜间补扫启用</span><input id="nightly_enabled" type="checkbox"></label>
        <label><span>夜间补扫小时</span><input id="nightly_hour" type="number" min="0" max="23" step="1"></label>
        <label><span>夜间补扫分钟</span><input id="nightly_minute" type="number" min="0" max="59" step="1"></label>
        <label><span>OP 搜索上限(秒)</span><input id="op_search_max_seconds" type="number" min="120" max="900" step="1"></label>
        <label><span>ED 尾部搜索(秒)</span><input id="ed_search_from_end_seconds" type="number" min="120" max="900" step="1"></label>
      </section>
    </div>

    <div class="grid" style="margin-top:16px;">
      <section class="card">
        <h2>算法开关</h2>
        <label><span>Dry Run</span><input id="dry_run" type="checkbox"></label>
        <label><span>ED 写第二段 Intro</span><input id="ed_pair" type="checkbox"></label>
        <label><span>优先原生章节</span><input id="chapter_detection_enabled" type="checkbox"></label>
        <label><span>最小相似度</span><input id="min_similarity" type="number" min="0.80" max="0.999" step="0.001"></label>
        <label><span>最小支持比例</span><input id="min_support_ratio" type="number" min="0.2" max="1" step="0.01"></label>
        <label><span>OP 位置容差(秒)</span><input id="op_tolerance" type="number" min="6" max="120" step="1"></label>
        <label><span>ED 尾部容差(秒)</span><input id="ed_tolerance" type="number" min="10" max="180" step="1"></label>
      </section>

      <section class="card">
        <h2>最近一次结果</h2>
        <pre id="lastReport">暂无</pre>
      </section>
    </div>

    <div class="grid" style="margin-top:16px;">
      <section class="card">
        <h2>最近报告</h2>
        <div id="reportsTable"></div>
      </section>
      <section class="card">
        <h2>候选剧季</h2>
        <div id="seasonsTable"></div>
      </section>
    </div>

    <section class="card" style="margin-top:16px;">
      <h2>批处理日志</h2>
      <div id="batchLogTable"></div>
    </section>
  </div>

  <script>
    async function getJson(url, options) {
      const resp = await fetch(url, options);
      if (!resp.ok) throw new Error(await resp.text());
      return await resp.json();
    }

    function toPre(obj) { return JSON.stringify(obj, null, 2); }

    function renderHealth(data) {
      const el = document.getElementById('health');
      el.innerHTML = `
        <div>状态</div><div class="${data.ok ? 'ok' : 'bad'}">${data.ok ? '正常' : '异常'}</div>
        <div>Emby</div><div>${data.emby_server_name || '-'}</div>
        <div>版本</div><div>${data.emby_version || '-'}</div>
        <div>Dry Run</div><div>${String(data.dry_run)}</div>
      `;
    }

    function renderScheduler(data) {
      const el = document.getElementById('scheduler');
      const rows = (data.jobs || []).map(job => `<div>${job.id}</div><div>${job.next_run_time || '-'}<br><span class="muted">${job.trigger}</span></div>`).join('');
      el.innerHTML = rows || '<div class="muted">暂无调度任务</div>';
    }

    function renderBatchStatus(data) {
      const percent = data.percent ?? 0;
      document.getElementById('batchBar').style.width = `${percent}%`;
      const current = data.current || {};
      const summary = data.summary || {};
      document.getElementById('batchMeta').innerHTML = `
        <div>状态</div><div>${data.status || 'idle'}</div>
        <div>完成</div><div>${data.completed || 0} / ${data.total || 0} (${percent}%)</div>
        <div>当前</div><div>${current.library || '-'} / ${current.series_name || '-'} / ${current.season_name || '-'}</div>
        <div>更新时间</div><div>${data.updated_at || '-'}</div>
        <div>OP 命中</div><div>${summary.op_detected ?? '-'} / ${summary.count ?? '-'}</div>
        <div>ED 命中</div><div>${summary.ed_detected ?? '-'} / ${summary.count ?? '-'}</div>
        <div>平均 OP support</div><div>${summary.avg_op_support ?? '-'}</div>
        <div>平均 ED support</div><div>${summary.avg_ed_support ?? '-'}</div>
      `;
      document.getElementById('batchStatus').textContent = toPre(data);
    }

    function renderSettings(data) {
      document.getElementById('dry_run').checked = !!data.dry_run;
      document.getElementById('ed_pair').checked = !!data.write_ed_as_second_intro_pair;
      document.getElementById('chapter_detection_enabled').checked = !!data.chapter_detection_enabled;
      document.getElementById('include_library_names').value = (data.include_library_names || []).join(',');
      document.getElementById('min_similarity').value = data.min_similarity ?? 0.92;
      document.getElementById('min_support_ratio').value = data.min_support_ratio ?? 0.34;
      document.getElementById('op_tolerance').value = data.op_position_tolerance_seconds ?? 36;
      document.getElementById('ed_tolerance').value = data.ed_tail_tolerance_seconds ?? 45;
      document.getElementById('poll_enabled').checked = !!data.poll_enabled;
      document.getElementById('poll_interval_minutes').value = data.poll_interval_minutes ?? 30;
      document.getElementById('nightly_enabled').checked = !!data.nightly_enabled;
      document.getElementById('nightly_hour').value = data.nightly_hour ?? 3;
      document.getElementById('nightly_minute').value = data.nightly_minute ?? 30;
      document.getElementById('discovery_min_episodes').value = data.discovery_min_episodes ?? 1;
      document.getElementById('op_search_max_seconds').value = data.op_search_max_seconds ?? 480;
      document.getElementById('ed_search_from_end_seconds').value = data.ed_search_from_end_seconds ?? 300;
    }

    function renderLibraries(data) {
      const el = document.getElementById('libraries');
      el.innerHTML = (data.available || []).map(item => {
        const active = (data.selected || []).includes(item.name);
        return `<span class="pill" style="${active ? 'background:#d9efe8;color:#0e7a5f;' : ''}">${item.name} (${item.collection_type || '-'})</span>`;
      }).join('');
      document.getElementById('effectiveRoots').textContent = toPre(data.effective_roots || []);
    }

    function renderReports(items) {
      const el = document.getElementById('reportsTable');
      if (!items.length) {
        el.innerHTML = '<div class="muted">暂无报告</div>';
        return;
      }
      el.innerHTML = `<table><thead><tr><th>文件</th><th>时间</th><th>大小</th></tr></thead><tbody>${
        items.map(item => `<tr><td>${item.name}</td><td>${item.modified_at}</td><td>${item.size_bytes}</td></tr>`).join('')
      }</tbody></table>`;
    }

    function renderSeasons(items) {
      const el = document.getElementById('seasonsTable');
      el.innerHTML = `<table><thead><tr><th>剧名</th><th>季</th><th>集数</th></tr></thead><tbody>${
        items.slice(0, 20).map(item => `<tr><td>${item.series_name}</td><td>${item.season_name}</td><td>${item.episode_count}</td></tr>`).join('')
      }</tbody></table>`;
    }

    function renderBatchLog(items) {
      const el = document.getElementById('batchLogTable');
      if (!items.length) {
        el.innerHTML = '<div class="muted">暂无批处理日志</div>';
        return;
      }
      el.innerHTML = `<table><thead><tr><th>剧名</th><th>季</th><th>OP</th><th>ED</th><th>策略/备注</th></tr></thead><tbody>${
        items.slice().reverse().map(item => {
          const op = item.op || {};
          const ed = item.ed || {};
          const opHeadline = op.headline || '-';
          const edHeadline = ed.headline || '-';
          return `<tr>
            <td>${item.series_name || '-'}</td>
            <td>${item.season_name || '-'}</td>
            <td>${op.method || '-'} / support ${op.support_episodes ?? '-'} / mean ${op.mean_similarity ?? '-'}<br><span class="muted">${opHeadline}</span></td>
            <td>${ed.method || '-'} / support ${ed.support_episodes ?? '-'} / mean ${ed.mean_similarity ?? '-'}<br><span class="muted">${edHeadline}</span></td>
            <td>OP notes: ${(op.notes || []).join(' | ') || '-'}<br>ED notes: ${(ed.notes || []).join(' | ') || '-'}</td>
          </tr>`;
        }).join('')
      }</tbody></table>`;
    }

    async function refreshAll() {
      const [health, status, seasons, reports, scheduler, libraries, batch, batchLog] = await Promise.all([
        getJson('/health'),
        getJson('/api/status'),
        getJson('/api/seasons'),
        getJson('/api/reports'),
        getJson('/api/scheduler'),
        getJson('/api/libraries'),
        getJson('/api/batch-status'),
        getJson('/api/batch-log')
      ]);
      renderHealth(health);
      renderSettings(status.runtime);
      renderScheduler(scheduler);
      renderLibraries(libraries);
      renderReports(reports.items);
      renderSeasons(seasons.items);
      renderBatchStatus(batch);
      renderBatchLog(batchLog.items || []);
      document.getElementById('lastReport').textContent = status.last_report ? toPre(status.last_report) : '暂无';
    }

    let refreshTimer = null;
    let refreshInFlight = false;

    async function autoRefreshTick() {
      if (refreshInFlight) return;
      refreshInFlight = true;
      try {
        await refreshAll();
      } finally {
        refreshInFlight = false;
      }
    }

    function startAutoRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      const intervalMs = document.hidden ? 15000 : 5000;
      refreshTimer = setInterval(autoRefreshTick, intervalMs);
    }

    async function saveSettings() {
      const payload = {
        dry_run: document.getElementById('dry_run').checked,
        write_ed_as_second_intro_pair: document.getElementById('ed_pair').checked,
        chapter_detection_enabled: document.getElementById('chapter_detection_enabled').checked,
        include_library_names: document.getElementById('include_library_names').value,
        min_similarity: Number(document.getElementById('min_similarity').value),
        min_support_ratio: Number(document.getElementById('min_support_ratio').value),
        op_position_tolerance_seconds: Number(document.getElementById('op_tolerance').value),
        ed_tail_tolerance_seconds: Number(document.getElementById('ed_tolerance').value),
        poll_enabled: document.getElementById('poll_enabled').checked,
        poll_interval_minutes: Number(document.getElementById('poll_interval_minutes').value),
        nightly_enabled: document.getElementById('nightly_enabled').checked,
        nightly_hour: Number(document.getElementById('nightly_hour').value),
        nightly_minute: Number(document.getElementById('nightly_minute').value),
        discovery_min_episodes: Number(document.getElementById('discovery_min_episodes').value),
        op_search_max_seconds: Number(document.getElementById('op_search_max_seconds').value),
        ed_search_from_end_seconds: Number(document.getElementById('ed_search_from_end_seconds').value),
      };
      await getJson('/api/runtime', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      await refreshAll();
      alert('已保存并立即生效');
    }

    async function runSample() {
      document.getElementById('lastReport').textContent = '正在跑样本季...';
      const result = await getJson('/api/jobs/run-sample', { method:'POST' });
      document.getElementById('lastReport').textContent = toPre(result);
      await refreshAll();
    }

    async function runTop3() {
      document.getElementById('lastReport').textContent = '正在跑 3 部动漫...';
      const result = await getJson('/api/jobs/run-top3', { method:'POST' });
      document.getElementById('lastReport').textContent = toPre(result);
      await refreshAll();
    }

    async function runPoll() {
      document.getElementById('lastReport').textContent = '正在执行轻量轮询...';
      const result = await getJson('/api/jobs/run-poll', { method:'POST' });
      document.getElementById('lastReport').textContent = toPre(result);
      await refreshAll();
    }

    async function runBackfill() {
      document.getElementById('lastReport').textContent = '正在执行夜间补扫...';
      const result = await getJson('/api/jobs/run-backfill', { method:'POST' });
      document.getElementById('lastReport').textContent = toPre(result);
      await refreshAll();
    }

    document.addEventListener('visibilitychange', () => {
      startAutoRefresh();
    });

    refreshAll().catch(err => {
      document.getElementById('lastReport').textContent = String(err);
    });
    startAutoRefresh();
  </script>
</body>
</html>"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    SERVICE.start()
    try:
        yield
    finally:
        SERVICE.stop()


app = FastAPI(title="Feiniu Emby Intro Marker", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return _page_html()


@app.get("/health")
def health() -> dict:
    try:
        return SERVICE.health()
    except Exception as exc:
        LOGGER.exception("Health check failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/status")
def status() -> dict:
    return {
        "config": {
            "emby_base_url": SETTINGS.emby_base_url,
            "db_path": str(SETTINGS.emby_db_path),
            "table": SETTINGS.emby_db_table,
            "media_roots": [str(path) for path in SETTINGS.media_roots],
        },
        "runtime": SERVICE.get_runtime_settings(),
        "last_report": SERVICE.last_report,
    }


@app.get("/api/scheduler")
def scheduler_status() -> dict:
    return SERVICE.get_scheduler_status()


@app.get("/api/libraries")
def libraries() -> dict:
    return SERVICE.get_library_status()


@app.get("/api/batch-status")
def batch_status() -> dict:
    return SERVICE.get_batch_status()


@app.get("/api/batch-log")
def batch_log() -> dict:
    return SERVICE.get_batch_log()


@app.get("/api/seasons")
def seasons() -> dict:
    return {"items": SERVICE.list_seasons()}


@app.get("/api/reports")
def reports() -> dict:
    return {"items": SERVICE.list_reports()}


@app.get("/api/runtime")
def runtime_settings() -> dict:
    return SERVICE.get_runtime_settings()


@app.post("/api/runtime")
def update_runtime_settings(payload: RuntimeSettingsPayload) -> dict:
    return SERVICE.update_runtime_settings(payload.model_dump(exclude_none=True))


@app.post("/api/jobs/run-sample")
def run_sample() -> dict:
    return SERVICE.run_sample_scan()


@app.post("/api/jobs/run-top3")
def run_top3() -> dict:
    return SERVICE.run_top_n_scan(count=3)


@app.post("/api/jobs/run-poll")
def run_poll() -> dict:
    return SERVICE.run_incremental_poll()


@app.post("/api/jobs/run-backfill")
def run_backfill() -> dict:
    return SERVICE.run_nightly_backfill()
