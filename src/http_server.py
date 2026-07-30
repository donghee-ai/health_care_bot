"""HTTP MJPEG + stats.json + 앱 제어 API + `/app` 정적 파일 제공.

기존 pose/scripts/infer_camera_pose.py 패턴 그대로:
  GET  /            → 디버그 index HTML
  GET  /stream.mjpg → multipart MJPEG
  GET  /stats.json  → 최신 상태 JSON (app 상태 포함)
  GET  /app/*       → 빌드된 React 앱 (web/dist) 정적 서빙
  POST /api/*       → PTZ/세션/제어권 API (APP_PLAN.md §9 데이터 계약)

로컬 네트워크 전용 - 공개 인터넷 노출 금지. 운영자 mutation은
app_state의 PIN 기반 제어권 lock으로만 보호된다 (그 외 인증 없음).
"""
import http.server
import json
import mimetypes
import socketserver
import threading
import time
from pathlib import Path

import cv2

import app_state

_state_lock = threading.Lock()
_latest_jpg = None
_latest_stats = {}
_latest_frame_ts_ms = 0.0

_viewer_lock = threading.Lock()
_viewer_count = 0

# main.py가 init_app()으로 주입하는 참조 - HTTP handler는 이걸 통해서만
# 추론 루프 객체(ptz/counter)에 접근한다.
_ptz = None
_squat_c = None
_overhead_c = None
_lateral_c = None
_avg_fps_fn = None

_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


def init_app(ptz=None, squat_c=None, overhead_c=None, lateral_c=None, avg_fps_fn=None):
    """main.py에서 추론 루프 시작 전 1회 호출 - API handler가 쓸 참조 등록."""
    global _ptz, _squat_c, _overhead_c, _lateral_c, _avg_fps_fn
    _ptz = ptz
    _squat_c = squat_c
    _overhead_c = overhead_c
    _lateral_c = lateral_c
    _avg_fps_fn = avg_fps_fn


def update_live_state(annotated_bgr, stats_dict, q=70, encode=True):
    """stats(숫자)와 jpg(영상)를 갱신.

    encode=False면 JPEG 인코딩을 건너뛰고 stats만 갱신한다 — main.py의
    --idle-skip-draw(연산 집중 모드)가 뷰어 0명일 때 쓴다. 인코딩을 생략해도
    stats.json은 계속 최신으로 흐른다. encode=True(기본)면 기존과 동일.
    """
    global _latest_jpg, _latest_stats, _latest_frame_ts_ms
    jpg = None
    if encode and annotated_bgr is not None:
        ok, buf = cv2.imencode('.jpg', annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok:
            jpg = buf.tobytes()
    with _state_lock:
        if jpg is not None:
            _latest_jpg = jpg
        _latest_stats = dict(stats_dict)
        _latest_frame_ts_ms = time.time() * 1000.0


def viewer_count() -> int:
    """지금 /stream.mjpg를 보는 뷰어 수 (main.py 게이팅용)."""
    with _viewer_lock:
        return _viewer_count


def _get_jpg():
    with _state_lock:
        return _latest_jpg


def _get_stats():
    with _state_lock:
        data = dict(_latest_stats)
        data["frame_ts_ms"] = round(_latest_frame_ts_ms, 1)
        return data


def _full_stats():
    data = _get_stats()
    with _viewer_lock:
        viewers = _viewer_count
    app_block = app_state.session_snapshot()
    control_block = app_state.control_snapshot()
    data["app"] = {
        "session": app_block,
        "control": control_block,
        "viewer_count": viewers,
    }
    if _ptz is not None:
        data["ptz"] = _ptz.snapshot()
    return data


_INDEX_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>UNO Q Health Care Bot</title>
<style>
body{font-family:system-ui,sans-serif;margin:16px;background:#111;color:#ddd;}
h2{color:#4fc3f7;margin:0 0 12px;}
.layout{display:flex;gap:16px;flex-wrap:wrap;}
.stream{flex:1 1 640px;}
.stream img{width:100%;max-width:960px;border:1px solid #555;border-radius:4px;background:#000;}
.stats{flex:0 1 380px;}
pre{background:#000;color:#8bc34a;padding:12px;border-radius:4px;overflow:auto;font-size:12px;line-height:1.4;max-height:80vh;}
.warn{color:#ff7043;font-size:12px;margin-top:8px;}
.tag{display:inline-block;padding:2px 6px;background:#333;border-radius:3px;font-size:11px;color:#aaa;margin-right:4px;}
a{color:#8ecdf7;}
</style></head><body>
<h2>UNO Q Health Care Bot
<span class="tag">squat + overhead + lateral</span><span class="tag">PTZ</span><span class="tag">MoveNet Thunder INT8</span></h2>
<p>모바일 앱: <a href="/app">/app</a> (viewer) · <a href="/app?role=operator">/app?role=operator</a> (operator)</p>
<div class="layout">
<div class="stream">
<img src="/stream.mjpg" alt="live">
<div class="warn">DEBUG ONLY. 인증 없음. 로컬 LAN 외부 노출 금지.</div>
</div>
<div class="stats"><pre id="stats">loading...</pre></div>
</div>
<script>
async function tick(){
  try{
    const r=await fetch('/stats.json',{cache:'no-store'});
    document.getElementById('stats').textContent=JSON.stringify(await r.json(),null,2);
  }catch(e){document.getElementById('stats').textContent='(lost: '+e.message+')';}
}
setInterval(tick,500);tick();
</script></body></html>
"""


def _json_body(handler) -> dict:
    length = int(handler.headers.get('Content-Length', 0) or 0)
    if length <= 0 or length > 65536:
        return {}
    try:
        raw = handler.rfile.read(length)
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {}


def _require_control(handler, body) -> bool:
    """운영자 제어권 lock을 갖고 있는지 확인. client_id는 body에서 온다."""
    client_id = str(body.get('client_id') or '')
    if not client_id or not app_state.has_control(client_id):
        _send_json(handler, 403, {"ok": False, "error": "control_not_claimed"})
        return False
    return True


def _send_json(handler, status: int, payload: dict):
    data = json.dumps(payload, default=str).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(data)))
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.end_headers()
    handler.wfile.write(data)


def _serve_static(handler, url_path: str):
    """`/app` 이하 경로를 web/dist에서 서빙. 없으면 index.html로 폴백 (SPA)."""
    rel = url_path[len('/app'):].lstrip('/')
    if not rel:
        rel = 'index.html'
    candidate = (_WEB_DIST / rel).resolve()
    try:
        candidate.relative_to(_WEB_DIST.resolve())
    except ValueError:
        handler.send_response(403)
        handler.end_headers()
        return
    if not candidate.is_file():
        candidate = _WEB_DIST / 'index.html'
    if not candidate.is_file():
        _send_json(handler, 503, {
            "ok": False,
            "error": "web_not_built",
            "hint": "cd web && npm install && npm run build",
        })
        return
    ctype = mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream'
    body = candidate.read_bytes()
    handler.send_response(200)
    handler.send_header('Content-Type', ctype)
    handler.send_header('Content-Length', str(len(body)))
    if candidate.suffix in ('.html',):
        handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    # ---------- GET ----------

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/', '/index.html'):
            body = _INDEX_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == '/stats.json':
            _send_json(self, 200, _full_stats())
        elif path == '/stream.mjpg':
            self._stream_mjpg()
        elif path == '/app' or path.startswith('/app/'):
            _serve_static(self, path)
        else:
            self.send_response(404)
            self.end_headers()

    def _stream_mjpg(self):
        global _viewer_count
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        with _viewer_lock:
            _viewer_count += 1
        try:
            while True:
                jpg = _get_jpg()
                if jpg is None:
                    time.sleep(0.05)
                    continue
                self.wfile.write(
                    b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                    + str(len(jpg)).encode() + b'\r\n\r\n'
                )
                self.wfile.write(jpg)
                self.wfile.write(b'\r\n')
                self.wfile.flush()
                time.sleep(0.03)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        finally:
            with _viewer_lock:
                _viewer_count = max(0, _viewer_count - 1)

    # ---------- POST ----------

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        path = self.path.split('?', 1)[0]
        body = _json_body(self)

        if path == '/api/control/claim':
            client_id = str(body.get('client_id') or '')
            pin = str(body.get('pin') or '')
            if not client_id:
                return _send_json(self, 400, {"ok": False, "error": "missing_client_id"})
            return _send_json(self, 200, app_state.claim_control(client_id, pin))

        if path == '/api/control/heartbeat':
            client_id = str(body.get('client_id') or '')
            return _send_json(self, 200, app_state.heartbeat_control(client_id))

        if path == '/api/control/release':
            client_id = str(body.get('client_id') or '')
            return _send_json(self, 200, app_state.release_control(client_id))

        if path == '/api/ptz':
            return self._handle_ptz(body)

        if path == '/api/mode':
            if not _require_control(self, body):
                return
            mode = str(body.get('mode') or '')
            return _send_json(self, 200, app_state.set_mode(mode))

        if path == '/api/session/start':
            if not _require_control(self, body):
                return
            target = body.get('target_reps')
            for _c in (_squat_c, _overhead_c, _lateral_c):
                if _c is not None:
                    _c.reset()
            return _send_json(self, 200, app_state.session_start(target))

        if path == '/api/session/pause':
            if not _require_control(self, body):
                return
            return _send_json(self, 200, app_state.session_pause())

        if path == '/api/session/resume':
            if not _require_control(self, body):
                return
            return _send_json(self, 200, app_state.session_resume())

        if path == '/api/session/reset':
            if not _require_control(self, body):
                return
            def reset_fn():
                for _c in (_squat_c, _overhead_c, _lateral_c):
                    if _c is not None:
                        _c.reset()
            return _send_json(self, 200, app_state.session_reset(reset_fn))

        if path == '/api/session/finish':
            if not _require_control(self, body):
                return
            snaps = {
                "squat": _squat_c.snapshot() if _squat_c is not None else None,
                "overhead": _overhead_c.snapshot() if _overhead_c is not None else None,
                "lateral": _lateral_c.snapshot() if _lateral_c is not None else None,
            }
            avg_fps = _avg_fps_fn() if _avg_fps_fn is not None else None
            return _send_json(self, 200, app_state.session_finish(snaps, avg_fps))

        self.send_response(404)
        self.end_headers()

    def _handle_ptz(self, body):
        if not _require_control(self, body):
            return
        if _ptz is None:
            return _send_json(self, 503, {"ok": False, "error": "ptz_unavailable"})

        command = str(body.get('command') or '')
        if command == 'pan':
            delta = max(-10.0, min(10.0, float(body.get('delta_deg', 0) or 0)))
            _ptz.set_auto_track(False)
            _ptz.manual_pan(delta)
        elif command == 'tilt':
            delta = max(-10.0, min(10.0, float(body.get('delta_deg', 0) or 0)))
            _ptz.set_auto_track(False)
            _ptz.manual_tilt(delta)
        elif command == 'center':
            _ptz.manual_center()
        elif command == 'auto_track':
            _ptz.set_auto_track(bool(body.get('enabled', True)))
        elif command == 'stop':
            _ptz.set_auto_track(False)
        else:
            return _send_json(self, 400, {"ok": False, "error": "unknown_command"})

        return _send_json(self, 200, {"ok": True, "ptz": _ptz.snapshot()})


class _TServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_server(port: int):
    """백그라운드 스레드로 HTTP 서버 시작. (server, thread) 반환."""
    srv = _TServer(('0.0.0.0', port), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, t
