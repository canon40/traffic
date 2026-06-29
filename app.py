import os
import threading
import time
from datetime import datetime, timedelta

from env_loader import load_env

load_env()

from flask import Flask, jsonify, render_template, request, send_from_directory

from rank_tracker import (
    build_completion_report,
    build_weekly_rank_report,
    format_weekly_report_markdown,
    get_history,
    load_config,
    save_config,
    save_weekly_report,
    track_all_keywords,
)
from seo_checker import get_latest_audit, run_full_audit
from keyword_analyzer import analyze_keyword, suggest_keywords_for_product, analyze_all_products
from seo_content_builder import generate_content, list_workflows, save_content
from rank_tracker import check_product_rank
from seo_blog_campaign import SeoBlogCampaignEngine

try:
    from data_store import cloud_enabled, pull_from_cloud, push_to_cloud
except ImportError:
    def cloud_enabled(): return False
    def pull_from_cloud(): return []
    def push_to_cloud(*a, **k): return []

app = Flask(__name__)

_pulled = pull_from_cloud()
if _pulled:
    print(f"[data_store] GCS에서 복원: {', '.join(_pulled)}")

_bg_bootstrapped = False


@app.before_request
def _bootstrap_cloud_background():
    global _bg_bootstrapped
    if _bg_bootstrapped:
        return
    if os.environ.get("AUTO_START_BACKGROUND", "").lower() not in ("1", "true", "yes"):
        return
    _bg_bootstrapped = True
    try:
        from cloud_background import start_cloud_services
        start_cloud_services()
    except Exception as e:
        print(f"[cloud_background] {e}")

logs_queue = []
scheduler_running = False
scheduler_thread = None
stop_event = threading.Event()
last_completion_report = None


def build_followup_schedule(base_time=None):
    now = base_time or datetime.now()
    offsets = [
        ("발행 후 6시간", 6),
        ("발행 후 24시간", 24),
        ("발행 후 48시간", 48),
    ]
    return [
        {
            "label": label,
            "hours_after_publish": hours,
            "scheduled_at": (now + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M"),
        }
        for label, hours in offsets
    ]


def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {msg}"
    print(formatted_msg)
    logs_queue.append(formatted_msg)
    if len(logs_queue) > 150:
        logs_queue.pop(0)


def scheduler_loop():
    global scheduler_running, last_completion_report
    add_log("🚀 순위 추적 스케줄러가 시작되었습니다.")
    cycle = 0

    while not stop_event.is_set():
        cycle += 1
        config = load_config()
        interval = max(5, int(config.get("track_interval_minutes", 60)))

        add_log(f"🔄 [사이클 {cycle}] 순위 추적 + SEO 점검 시작")
        results = track_all_keywords(logger=add_log)
        report = build_completion_report(results)
        last_completion_report = report

        for item in report.get("items", []):
            if item.get("status") != "실패":
                add_log(f"📊 {item['keyword']}: {item.get('detail', '')}")

        add_log(f"✅ {report['summary']}")

        try:
            from data_store import push_to_cloud
            push_to_cloud(("rank_history.csv",))
        except Exception:
            pass

        if cycle == 1 or cycle % 6 == 0:
            add_log("🔎 정기 SEO 체크리스트 점검 실행...")
            audit = run_full_audit(logger=add_log)
            avg = audit["summary"].get("average_score", 0)
            add_log(f"📋 SEO 평균 점수: {avg}점 (점검 {audit['summary']['audited_ok']}페이지)")

        add_log(f"😴 다음 추적까지 {interval}분 대기")
        for _ in range(interval * 6):
            if stop_event.is_set():
                break
            time.sleep(10)

    scheduler_running = False
    add_log("🛑 순위 추적 스케줄러가 중지되었습니다.")


def generate_daily_report():
    history = get_history()
    if not history:
        return "아직 순위 기록이 없습니다. '지금 추적' 버튼을 눌러 첫 기록을 만드세요."

    recent = history[-10:]
    lines = ["### 📊 일일 순위 리포트", f"- 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    for row in recent:
        kw = row.get("키워드", "")
        rank = row.get("순위", "-")
        change = row.get("변동", "-")
        task = row.get("작업유형", "")
        detail = row.get("상세", "")
        lines.append(f"- **{kw}**: {detail} (변동: {change}, 작업: {task})")

    audit = get_latest_audit()
    if audit:
        lines.extend([
            "",
            "### 🔎 최근 SEO 점검",
            f"- 평균 점수: {audit['summary'].get('average_score', 0)}점",
            f"- 점검 페이지: {audit['summary'].get('audited_ok', 0)}개",
        ])
        recs = audit["summary"].get("recommendations", [])[:5]
        if recs:
            lines.append("- 개선 권장:")
            for r in recs:
                lines.append(f"  - {r}")

    return "\n".join(lines)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    history = get_history()
    last_rank = None
    if history:
        try:
            last_rank = int(history[-1].get("순위", 100))
        except (TypeError, ValueError):
            last_rank = 100

    config = load_config()
    return jsonify({
        "running": scheduler_running,
        "last_rank": last_rank,
        "total_tracks": len(history),
        "keyword_count": len(config.get("keywords", [])),
        "interval_minutes": config.get("track_interval_minutes", 60),
        "last_report": last_completion_report,
    })


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify(load_config())
    data = request.get_json(silent=True) or {}
    config = load_config()
    for key in ("store_name", "brand", "track_interval_minutes", "keywords", "products", "product_urls", "blog_urls"):
        if key in data:
            config[key] = data[key]
    save_config(config)
    add_log("⚙️ 설정이 저장되었습니다.")
    return jsonify({"success": True, "config": config})


@app.route("/api/track-now", methods=["POST"])
def api_track_now():
    global last_completion_report
    add_log("📱 수동 순위 추적 요청")
    results = track_all_keywords(logger=add_log)
    report = build_completion_report(results)
    last_completion_report = report
    pushed = push_to_cloud(("rank_history.csv",))
    if pushed:
        add_log(f"☁️ 클라우드 저장: {', '.join(pushed)}")
    add_log(f"✅ {report['summary']}")
    return jsonify({"success": True, "report": report})


@app.route("/api/seo-audit", methods=["POST"])
def api_seo_audit():
    add_log("📱 SEO 체크리스트 점검 요청")
    audit = run_full_audit(logger=add_log)
    add_log(f"📋 SEO 평균 점수: {audit['summary'].get('average_score', 0)}점")
    return jsonify({"success": True, "audit": audit})


@app.route("/api/seo-audit/latest")
def api_seo_audit_latest():
    audit = get_latest_audit()
    return jsonify({"audit": audit})


@app.route("/api/start", methods=["POST"])
def api_start():
    global scheduler_running, scheduler_thread, stop_event
    if not scheduler_running:
        stop_event.clear()
        scheduler_running = True
        scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        scheduler_thread.start()
        add_log("▶️ 자동 순위 추적을 시작했습니다.")
        return jsonify({"success": True, "message": "자동 순위 추적이 시작되었습니다."})
    return jsonify({"success": False, "message": "이미 실행 중입니다."})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global scheduler_running, stop_event
    if scheduler_running:
        stop_event.set()
        add_log("⏸️ 자동 추적 중지 요청")
        return jsonify({"success": True, "message": "중지 명령이 전달되었습니다."})
    return jsonify({"success": False, "message": "실행 중이 아닙니다."})


@app.route("/api/logs")
def api_logs():
    return jsonify({"logs": logs_queue})


@app.route("/api/history")
def api_history():
    return jsonify(get_history())


@app.route("/api/report")
def api_report():
    return jsonify({"report": generate_daily_report()})


@app.route("/api/rank/weekly")
def api_rank_weekly():
    days = request.args.get("days", 7, type=int)
    days = max(1, min(days, 90))
    report = build_weekly_rank_report(days=days)
    return jsonify({
        "success": True,
        "report": report,
        "markdown": format_weekly_report_markdown(report),
    })


@app.route("/api/rank/weekly/save", methods=["POST"])
def api_rank_weekly_save():
    data = request.get_json(silent=True) or {}
    days = max(1, min(int(data.get("days", 7)), 90))
    report = build_weekly_rank_report(days=days)
    json_path, csv_path = save_weekly_report(report)
    add_log(f"📅 주간 순위 리포트 저장 ({days}일)")
    return jsonify({
        "success": True,
        "report": report,
        "json_path": json_path,
        "csv_path": csv_path,
    })


@app.route("/api/traffic/report")
def api_traffic_report():
    from traffic_session_log import build_campaign_report, format_report_markdown

    days = request.args.get("days", 30, type=int)
    days = max(1, min(days, 90))
    report = build_campaign_report(days=days)
    return jsonify({
        "success": True,
        "report": {k: v for k, v in report.items() if k != "sessions"},
        "markdown": format_report_markdown(report),
    })


@app.route("/api/traffic/report/save", methods=["POST"])
def api_traffic_report_save():
    from traffic_session_log import build_campaign_report, save_report

    data = request.get_json(silent=True) or {}
    days = max(1, min(int(data.get("days", 30)), 90))
    report = build_campaign_report(days=days)
    json_path, md_path = save_report(report)
    add_log(f"📊 트래픽 결과 리포트 저장 ({days}일)")
    return jsonify({
        "success": True,
        "report": {k: v for k, v in report.items() if k != "sessions"},
        "json_path": json_path,
        "md_path": md_path,
    })


@app.route("/api/completion")
def api_completion():
    return jsonify({"report": last_completion_report})


@app.route("/api/keyword/analyze", methods=["POST"])
def api_keyword_analyze():
    data = request.get_json(silent=True) or {}
    keyword = data.get("keyword", "")
    product_id = data.get("product_id")
    result = analyze_keyword(keyword, product_id=product_id)
    if result.get("success"):
        add_log(f"🔑 키워드 분석: {keyword} — {result.get('opportunity_score')}점")
    return jsonify(result)


@app.route("/api/keyword/suggest", methods=["POST"])
def api_keyword_suggest():
    data = request.get_json(silent=True) or {}
    name = data.get("product_name", "퍼마코트")
    suggestions = suggest_keywords_for_product(name)
    return jsonify({"success": True, "suggestions": suggestions})


@app.route("/api/product/rank", methods=["POST"])
def api_product_rank():
    data = request.get_json(silent=True) or {}
    keyword = data.get("keyword", "")
    product_id = data.get("product_id", "")
    rank = check_product_rank(keyword, product_id)
    display = f"{rank}위" if rank and rank < 100 else "100위 밖"
    return jsonify({"success": rank is not None, "rank": rank, "display": display})


@app.route("/api/content/workflows")
def api_content_workflows():
    return jsonify({"workflows": list_workflows()})


@app.route("/api/content/generate", methods=["POST"])
def api_content_generate():
    data = request.get_json(silent=True) or {}
    result = generate_content(
        data.get("workflow", "product_detail"),
        data.get("keyword", ""),
        data.get("product_name"),
        data.get("brand"),
    )
    if result.get("success"):
        path = save_content(result, data.get("product_id"))
        result["saved_path"] = path
        add_log(f"📝 콘텐츠 생성: {result.get('workflow_label')}")
    return jsonify(result)


@app.route("/api/seo-fixes", methods=["GET", "POST"])
def api_seo_fixes():
    from seo_fixes import run as generate_seo_fixes

    manifest = generate_seo_fixes()
    add_log("📋 SEO 붙여넣기 가이드·블로그 초안 생성 완료")
    return jsonify({"success": True, **manifest})


@app.route("/api/seo-fixes/guide")
def api_seo_fixes_guide():
    path = os.path.join("generated_content", "SEO_붙여넣기_가이드.md")
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "가이드 없음. /api/seo-fixes 먼저 실행"})
    with open(path, "r", encoding="utf-8") as f:
        return jsonify({"success": True, "content": f.read()})


@app.route("/api/keyword/progress")
def api_keyword_progress():
    from keyword_progress import build_keyword_progress_board

    days = request.args.get("days", 30, type=int)
    days = max(1, min(days, 90))
    board = build_keyword_progress_board(days=days)
    return jsonify({"success": True, "board": board})


@app.route("/api/cron/rank-sweep", methods=["POST", "GET"])
def api_cron_rank_sweep():
    """외부 스케줄러(Cloud Scheduler 등) → API 순위 스윕 + GCS 동기화."""
    secret = os.environ.get("CRON_SECRET", "")
    provided = request.headers.get("X-Cron-Secret") or request.args.get("key", "")
    if secret and provided != secret:
        return jsonify({"success": False, "error": "unauthorized"}), 401

    from rank_tracker import build_completion_report, track_all_keywords
    from env_loader import api_keys_status

    results = track_all_keywords(logger=add_log)
    report = build_completion_report(results)
    pushed = push_to_cloud(("rank_history.csv",))
    return jsonify({
        "success": True,
        "summary": report.get("summary"),
        "found": sum(1 for r in results if not r.get("not_found")),
        "total": len(results),
        "api_keys": api_keys_status(),
        "cloud_sync": pushed,
    })


@app.route("/api/cron/daily-rank", methods=["POST", "GET"])
def api_cron_daily_rank():
    """Google Cloud Scheduler → Cloud Run 호출용."""
    secret = os.environ.get("CRON_SECRET", "")
    provided = request.headers.get("X-Cron-Secret") or request.args.get("key", "")
    if secret and provided != secret:
        return jsonify({"success": False, "error": "unauthorized"}), 401

    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "daily_rank_track.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
    )
    pushed = push_to_cloud(("rank_history.csv",))
    return jsonify({
        "success": proc.returncode == 0,
        "exit_code": proc.returncode,
        "cloud_sync": pushed,
        "stderr_tail": (proc.stderr or "")[-500:],
    })


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "ts": datetime.now().isoformat()})


@app.route("/api/background/status")
def api_background_status():
    try:
        from cloud_background import background_status
        return jsonify({"success": True, **background_status()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cloud/status")
def api_cloud_status():
    from env_loader import api_keys_status
    keys = api_keys_status()
    return jsonify({
        "cloud_storage": cloud_enabled(),
        "bucket": os.environ.get("GCS_BUCKET") or os.environ.get("GCS_DATA_BUCKET"),
        "rank_api": keys,
        "rank_use_api": os.environ.get("RANK_USE_API", "auto"),
        "note": (
            "API 순위(SerpAPI/CSE) + GCS로 Cloudtype 24h 순위 추적 가능. "
            "Playwright 트래픽은 GCP VM/로컬 run_focus_24h.bat 필요."
            if keys.get("serpapi") or keys.get("google_cse")
            else "SERPAPI_KEY 또는 GOOGLE_API_KEY+CSE_ID를 Cloudtype 환경변수에 설정하세요."
        ),
    })


@app.route("/api/rank/followups")
def api_rank_followups():
    return jsonify({"success": True, "schedule": build_followup_schedule()})


@app.route("/api/blog/regenerate", methods=["POST"])
def api_blog_regenerate():
    data = request.get_json(silent=True) or {}
    product_name = data.get("product_name", "")
    count = max(1, int(data.get("count", 3)))
    use_report = bool(data.get("from_report", True))

    add_log(f"📝 블로그 초안 재생성 요청: {product_name or '전체'} / {count}건")
    engine = SeoBlogCampaignEngine(logger=add_log)
    saved = engine.run_campaign(
        target_product_name=product_name or None,
        posts_per_product=count,
        use_report=use_report,
    )
    return jsonify({"success": True, "saved": saved, "count": len(saved)})


@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js")


@app.route("/openapi.json")
def openapi_spec():
    return send_from_directory(".", "openapi.json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
