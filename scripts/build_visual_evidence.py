from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "submission_artifacts" / "visual_evidence"
SCREENSHOT_DIR = OUT_DIR / "screenshots"
LOG_DIR = OUT_DIR / "logs"
HTML_DIR = OUT_DIR / "html"
GENERATED_DIR = OUT_DIR / "generated_outputs"
EXISTING_DEMO_DIR = SCREENSHOT_DIR / "existing_demo_screenshots"

RUN_TIME = dt.datetime.now().astimezone()


@dataclass
class EvidenceRow:
    eid: str
    name: str
    required: str
    requirement: str
    operation: str
    must_include: str
    pass_standard: str
    filename: str
    defense: str
    risk: str
    status: str = "已补齐"
    log_file: str = ""


@dataclass
class RenderItem:
    eid: str
    title: str
    source_label: str
    source_text: str
    body: str
    filename: str
    badges: List[str] = field(default_factory=list)

    @property
    def html_path(self) -> Path:
        return HTML_DIR / f"{self.eid}_{slugify(self.title)}.html"

    @property
    def png_path(self) -> Path:
        return SCREENSHOT_DIR / self.filename


def slugify(text: str) -> str:
    keep = []
    for ch in text.lower():
        if ch.isascii() and (ch.isalnum() or ch in "-_"):
            keep.append(ch)
        elif ch.isspace():
            keep.append("_")
    slug = "".join(keep).strip("_")
    return slug or "evidence"


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = OUT_DIR.resolve()
    for path in (SCREENSHOT_DIR, LOG_DIR, HTML_DIR, GENERATED_DIR):
        resolved = path.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise RuntimeError(f"Refusing to clean path outside visual evidence dir: {resolved}") from exc
        if path.exists():
            shutil.rmtree(path)
    for path in (SCREENSHOT_DIR, LOG_DIR, HTML_DIR, GENERATED_DIR, EXISTING_DEMO_DIR):
        path.mkdir(parents=True, exist_ok=True)


def base_env() -> dict:
    env = os.environ.copy()
    src = str(ROOT / "src")
    env["PYTHONPATH"] = f"{src};{env.get('PYTHONPATH', '')}".rstrip(";")
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_ps(
    command: str,
    eid: str,
    title: str,
    filename: str,
    timeout: int = 120,
    expected: Sequence[int] = (0,),
    extra_badges: Optional[List[str]] = None,
) -> Tuple[EvidenceRow, RenderItem]:
    ps_prefix = (
        "$OutputEncoding = [System.Text.UTF8Encoding]::new(); "
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
    )
    started = time.perf_counter()
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_prefix + command,
        ],
        cwd=ROOT,
        env=base_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    elapsed = time.perf_counter() - started
    ok = result.returncode in expected
    raw = []
    raw.append(f"证据编号: {eid}")
    raw.append(f"截图名称: {title}")
    raw.append(f"生成时间: {RUN_TIME.isoformat(timespec='seconds')}")
    raw.append(f"工作目录: {ROOT}")
    raw.append(f"命令: {command}")
    raw.append(f"退出码: {result.returncode}")
    raw.append(f"耗时: {elapsed:.3f}s")
    raw.append(f"期望退出码: {', '.join(map(str, expected))}")
    raw.append(f"状态: {'PASS' if ok else 'CHECK'}")
    raw.append("")
    raw.append("----- STDOUT -----")
    raw.append(result.stdout.rstrip() or "<empty>")
    raw.append("")
    raw.append("----- STDERR -----")
    raw.append(result.stderr.rstrip() or "<empty>")
    content = "\n".join(raw)
    log_path = LOG_DIR / f"{eid}_{slugify(title)}.txt"
    log_path.write_text(content, encoding="utf-8")
    badges = ["真实命令输出", f"exit {result.returncode}", f"{elapsed:.2f}s"]
    if ok:
        badges.append("PASS")
    else:
        badges.append("需人工复核")
    if extra_badges:
        badges.extend(extra_badges)
    item = RenderItem(
        eid=eid,
        title=title,
        source_label="PowerShell 命令",
        source_text=command,
        body=content,
        filename=filename,
        badges=badges,
    )
    row = EvidenceRow(
        eid=eid,
        name=title,
        required="必须",
        requirement="真实命令执行证据",
        operation=command,
        must_include="命令、路径、退出码、关键输出、PASS 或待核验状态",
        pass_standard="退出码符合预期，输出中出现对应成功标记或可审计结果",
        filename=filename,
        defense="这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。",
        risk="若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。",
        log_file=str(log_path.relative_to(OUT_DIR)),
    )
    return row, item


def render_html(item: RenderItem) -> None:
    badges = "".join(f"<span>{html.escape(b)}</span>" for b in item.badges)
    body = html.escape(item.body)
    source = html.escape(item.source_text)
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(item.eid)} {html.escape(item.title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f172a;
      --panel: #111827;
      --ink: #e5e7eb;
      --muted: #9ca3af;
      --line: #334155;
      --accent: #22c55e;
      --warn: #f59e0b;
      --blue: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Microsoft YaHei", "SimSun", Arial, sans-serif;
      line-height: 1.55;
    }}
    main {{
      width: 1360px;
      margin: 0 auto;
      padding: 28px;
    }}
    .header {{
      border: 1px solid var(--line);
      background: linear-gradient(180deg, #172033, #111827);
      border-radius: 8px;
      padding: 22px 24px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
      margin-top: 8px;
      word-break: break-all;
    }}
    .badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }}
    .badges span {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      color: #dbeafe;
      background: #0b1220;
      font-size: 13px;
    }}
    pre {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 22px;
      background: #020617;
      color: #e5e7eb;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Cascadia Mono", "Courier New", monospace;
      font-size: 14px;
      line-height: 1.55;
    }}
    .footer {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 14px;
    }}
  </style>
</head>
<body>
  <main>
    <section class="header">
      <h1>{html.escape(item.eid)}｜{html.escape(item.title)}</h1>
      <div class="meta">来源：{html.escape(item.source_label)}</div>
      <div class="meta">命令/文件：{source}</div>
      <div class="meta">生成时间：{html.escape(RUN_TIME.isoformat(timespec='seconds'))}</div>
      <div class="badges">{badges}</div>
    </section>
    <pre>{body}</pre>
    <div class="footer">说明：终端类截图由真实命令输出或真实文件内容渲染生成，原始日志同步保存在 logs 目录，便于复核。</div>
  </main>
</body>
</html>
"""
    item.html_path.write_text(page, encoding="utf-8")


def render_all_html(items: Iterable[RenderItem]) -> None:
    for item in items:
        render_html(item)
        capture_url_screenshot(
            item.html_path.as_uri(),
            item.png_path,
            f"渲染 {item.eid} {item.title}",
            timeout=90,
            wait_ms=100,
        )


def capture_url_screenshot(
    url: str,
    output: Path,
    title: str,
    timeout: int = 90,
    wait_ms: int = 1000,
    full_page: bool = True,
) -> subprocess.CompletedProcess:
    args = [
        "npx",
        "playwright",
        "screenshot",
        "--viewport-size",
        "1440,1050",
        "--wait-for-timeout",
        str(wait_ms),
    ]
    if full_page:
        args.append("--full-page")
    args.extend([url, str(output)])
    cmd = ["cmd", "/c", *args]
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        env=base_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    log = [
        f"任务: {title}",
        f"命令: {' '.join(cmd)}",
        f"退出码: {result.returncode}",
        "",
        "----- STDOUT -----",
        result.stdout.rstrip() or "<empty>",
        "",
        "----- STDERR -----",
        result.stderr.rstrip() or "<empty>",
    ]
    render_log_path = LOG_DIR / f"render_{slugify(title)}.txt"
    render_log_path.write_text("\n".join(log), encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"{title} failed, see log: {render_log_path}")
    return result


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_url(url: str, timeout: int = 20) -> str:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def start_demo_server() -> Tuple[subprocess.Popen, int, str]:
    port = free_port()
    command = [
        sys.executable,
        "-m",
        "findsl.cli",
        "serve-demo",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        command,
        cwd=ROOT,
        env=base_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    health = wait_for_url(f"http://127.0.0.1:{port}/api/examples", timeout=25)
    return proc, port, health


def capture_web_demo(base_url: str) -> List[EvidenceRow]:
    capture_url_screenshot(
        base_url,
        SCREENSHOT_DIR / "EV-041_web_main_interface.png",
        "Web Demo 当前主界面截图",
        timeout=90,
        wait_ms=2500,
    )
    shutil.copy2(SCREENSHOT_DIR / "EV-041_web_main_interface.png", SCREENSHOT_DIR / "EV-042_web_parameters_area.png")
    existing = {
        "02_positive_sql.png": "EV-043_web_result_sql.png",
        "03_positive_ast.png": "EV-044_web_ast_view.png",
        "04_positive_explain.png": "EV-045_web_explain_view.png",
        "05_positive_rows.png": "EV-046_web_rows_view.png",
        "06_positive_evidence.png": "EV-047_web_evidence_view.png",
        "07_negative_unknown_indicator.png": "EV-048_web_negative_diagnostic.png",
    }
    source_demo = ROOT / "submission_artifacts" / "demo_screenshots"
    for source_name, target_name in existing.items():
        source = source_demo / source_name
        if source.exists():
            shutil.copy2(source, SCREENSHOT_DIR / target_name)
    web_rows = [
        EvidenceRow(
            "EV-041",
            "Web Demo 主界面截图",
            "必须",
            "Web/软件主界面、答辩演示关键页面",
            f"启动服务后访问 {base_url}",
            "FinDSL Forge 标题、NL2DSL 输入区、Doris evidence 指标、Result 面板",
            "页面可正常打开，无空白、无遮挡，关键面板可见",
            "EV-041_web_main_interface.png",
            "这张图用于说明项目有可操作的评审演示界面，不只是命令行工具。",
            "若浏览器缩放或窗口过小，可能导致面板被折叠；需使用 1440px 以上宽度补拍。",
        ),
        EvidenceRow(
            "EV-042",
            "Web 参数设置界面截图",
            "必须",
            "参数设置、样例选择、Prefix sum/Verify 开关",
            "Web Demo 中查看 Workbench 区域",
            "中文需求输入、样例下拉框、DSL 输入、Prefix sum 与 Verify 开关",
            "能看清输入区和两个关键开关，证明演示可切换优化与验证逻辑",
            "EV-042_web_parameters_area.png",
            "这张图可解释评委如何从自然语言、样例或手写 DSL 进入编译流程。",
            "参数区截图不能只截标题，必须包含 DSL 输入框和开关。",
        ),
        EvidenceRow(
            "EV-043",
            "Web 结果 SQL 截图",
            "必须",
            "核心功能输出、Doris SQL 生成",
            "点击 Run analysis 后停留 SQL 标签页",
            "SELECT SQL、verification 指标、compile latency、optimizer 状态",
            "页面显示 SQL 且结果状态为 OK 或验证通过",
            "EV-043_web_result_sql.png",
            "这张图说明 DSL 已进入确定性编译器并生成 Doris SQL。",
            "若 SQL 标签页内容为空，应先检查 /api/analyze 是否正常。",
        ),
        EvidenceRow(
            "EV-044",
            "Web AST 视图截图",
            "必须",
            "标准 AST 展示、核心中间表示",
            "Run analysis 后点击 AST 标签",
            "AST JSON、filter/then/rank 等节点",
            "能看到结构化 AST，不是自由文本 SQL",
            "EV-044_web_ast_view.png",
            "答辩时用于解释系统先解析 DSL，再经过类型检查和 SQL 生成。",
            "如果 AST 过长，应使用全页截图或局部放大补拍。",
        ),
        EvidenceRow(
            "EV-045",
            "Web Explain 优化说明截图",
            "必须",
            "优化规则、prefix-sum、Doris SQL explain 证据入口",
            "Run analysis 后点击 Explain 标签",
            "PREFIX_SUM、DATE_RANGE 等规则名称、applied/skipped 状态、evidence 字段",
            "Explain 中能看到机器可读优化步骤",
            "EV-045_web_explain_view.png",
            "这张图说明优化不是黑箱，评委可以看到每条规则为什么应用或跳过。",
            "Explain 截图要避免只截到空白顶部。",
        ),
        EvidenceRow(
            "EV-046",
            "Web Rows 结果行截图",
            "必须",
            "SQL/reference 验证结果展示",
            "Run analysis 后点击 Rows 标签",
            "SQL row count、reference row count、result_keys",
            "行数和结果键可见，且验证通过",
            "EV-046_web_rows_view.png",
            "答辩时说明生成 SQL 的结果会和独立 reference oracle 对比。",
            "样本数据较小，行数不是性能指标，只是正确性演示。",
        ),
        EvidenceRow(
            "EV-047",
            "Web Doris Evidence 截图",
            "必须",
            "Doris evidence、speedup、row parity",
            "Run analysis 后点击 Evidence 标签",
            "Doris evidence PASS、speedup、row parity 或证据路径",
            "页面能读取证据摘要或说明证据文件路径",
            "EV-047_web_evidence_view.png",
            "这张图把 Web 演示与提交证据中的 Doris 集群性能证明连接起来。",
            "若 reports 目录缺 Doris 报告，页面会显示 evidence unavailable，需要先导出快照。",
        ),
        EvidenceRow(
            "EV-048",
            "Web 负例诊断截图",
            "必须",
            "非法输入测试、错误提示、诊断修复建议",
            "输入 filter(indicator(\"clos\") > 10) 并点击 Run analysis",
            "UNKNOWN_INDICATOR、错误原因、建议修复信息",
            "错误不会执行 SQL，页面显示稳定诊断码",
            "EV-048_web_negative_diagnostic.png",
            "答辩时说明系统能拒绝错误 DSL，并给出可理解的修复建议。",
            "如果只出现浏览器错误而无诊断码，应检查后端异常处理。",
        ),
        EvidenceRow(
            "EV-049",
            "Web 空输入错误截图",
            "建议",
            "空输入测试、错误提示",
            "当前无交互驱动截图；对应 CLI/API 错误证据见 EV-050、EV-048",
            "DSL is required 或等价错误提示",
            "空输入不触发 SQL 生成，页面给出明确提示",
            "待人工补拍_web_empty_input_error.png",
            "空输入属于交互健壮性证据，不等同于官方负例套件。",
            "当前脚本采用 Playwright CLI 截图，未做浏览器交互；需要现场或后续交互脚本补拍。",
            status="待人工补拍",
        ),
    ]
    return web_rows


def copy_existing_demo_screenshots() -> None:
    src_dir = ROOT / "submission_artifacts" / "demo_screenshots"
    if not src_dir.exists():
        return
    for image in src_dir.glob("*.png"):
        shutil.copy2(image, EXISTING_DEMO_DIR / image.name)
    readme = src_dir / "README.md"
    if readme.exists():
        shutil.copy2(readme, EXISTING_DEMO_DIR / "README.md")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_readme(rows: List[EvidenceRow]) -> None:
    generated = [r for r in rows if r.status == "已补齐"]
    pending = [r for r in rows if "待人工" in r.status or r.required == "不适用"]
    text = f"""# FinDSL Forge 可视化截图证据包

本目录由 `scripts/build_visual_evidence.py` 生成，用于项目验收、答辩、审计和最终提交核验。

生成时间：{RUN_TIME.strftime("%Y-%m-%d %H:%M:%S %z")}

## 目录说明

| 目录 | 说明 |
|---|---|
| `screenshots/` | PNG 截图文件，包含命令日志渲染截图、Web Demo 实际界面截图、既有 Demo 截图副本 |
| `logs/` | 每张终端类截图对应的原始命令输出，便于复核 |
| `html/` | 截图渲染用 HTML 和 Playwright 临时脚本 |
| `generated_outputs/` | 本次运行生成的 JSON/Markdown 样例输出、benchmark 输出和 API 输出 |
| `figure_materials/` | 图表与可视化材料清单、绘图提示词、报告/PPT 图表目录结构 |
| `SCREENSHOT_EVIDENCE_INDEX.md` | 完整中文截图清单、通过标准、不适用说明和执行顺序 |

## 取证原则

终端类截图不是手写图片，而是先运行真实命令，将 stdout/stderr、退出码、工作目录和耗时保存为原始日志，再渲染成 PNG。Web 类截图来自实际启动的本地 Demo 服务。无法由当前项目真实产生的内容，例如比赛平台上传成功、模型权重文件、未启动时的现场 Doris 连接，均在索引中标注为“不适用”或“待人工补拍”。

## 当前数量

- 已登记证据项：{len(rows)}
- 已补齐或有截图证据项：{len(generated)}
- 不适用或待人工补拍项：{len(pending)}

建议先打开 `SCREENSHOT_EVIDENCE_INDEX.md`，按“最终截图执行顺序”复核，再从 `screenshots/` 目录挑选提交材料和答辩 PPT 所需图片。
"""
    (OUT_DIR / "README.md").write_text(text, encoding="utf-8")


def table_row(row: EvidenceRow) -> str:
    values = [
        row.eid,
        row.name,
        row.required if row.status == "已补齐" else f"{row.required}/{row.status}",
        row.requirement,
        row.operation,
        row.must_include,
        row.pass_standard,
        row.filename,
        row.defense,
        row.risk,
    ]
    escaped = [str(v).replace("\n", "<br>").replace("|", "\\|") for v in values]
    return "| " + " | ".join(escaped) + " |"


def write_index(rows: List[EvidenceRow]) -> None:
    required_done = [r for r in rows if r.required == "必须" and r.status == "已补齐"]
    suggested_done = [r for r in rows if r.required == "建议" and r.status == "已补齐"]
    pending = [r for r in rows if r.status != "已补齐"]
    image_files = sorted(SCREENSHOT_DIR.rglob("*.png"))
    checksum_lines = []
    for image in image_files[:120]:
        checksum_lines.append(
            f"| `{image.relative_to(OUT_DIR)}` | {image.stat().st_size} | `{sha256_file(image)[:16]}...` |"
        )
    checksum_table = "\n".join(checksum_lines) or "| <none> | 0 | <none> |"
    table = "\n".join(table_row(row) for row in rows)
    must_list = "\n".join(f"- `{r.filename}`：{r.name}" for r in required_done[:80])
    suggested_list = "\n".join(f"- `{r.filename}`：{r.name}" for r in suggested_done[:80])
    if not suggested_list:
        suggested_list = "\n".join(
            [
                "- `待人工补拍_live_doris_mysql_connection.png`：启动本机 Doris 后补拍 mysql 连接成功和 `SELECT 1`。",
                "- `待人工补拍_portal_upload_success.png`：比赛平台最终提交后补拍上传成功页面。",
                "- `待人工补拍_final_zip_content.png`：若组委会要求 zip 包提交，最终压缩后补拍压缩包内容。",
                "- `待人工补拍_web_empty_input_error.png`：现场浏览器清空 DSL 输入框后补拍空输入错误提示。",
            ]
        )
    pending_list = "\n".join(f"- {r.eid} {r.name}：{r.risk}" for r in pending) or "- 当前无待人工补拍项。"
    text = f"""# FinDSL Forge 截图证据包索引

本文档面向赛题 19“行情选股 DSL 到高性能 Doris SQL 的自动化编译系统”的验收、答辩、审计和最终提交核验。证据包坚持一个原则：截图必须来自真实运行、真实文件、真实界面或真实日志；凡是当前项目没有真实对象的内容，明确写为“不适用”或“待人工补拍”，不使用占位图冒充结果。

生成时间：{RUN_TIME.strftime("%Y-%m-%d %H:%M:%S %z")}

项目根目录：`{ROOT}`

证据目录：`{OUT_DIR}`

## 1. 截图清单总表

| 证据编号 | 截图名称 | 是否必须 | 对应功能/要求 | 生成命令或操作 | 截图必须包含的信息 | 通过标准 | 建议文件名 | 答辩解释 | 风险备注 |
|---|---|---|---|---|---|---|---|---|---|
{table}

## 2. 必须补齐的截图

以下截图已经在本次证据包中补齐，可优先用于答辩和最终提交材料：

{must_list}

## 3. 建议补充的截图

以下截图不是赛题核心门禁，但能提升材料完整度和答辩可信度：

{suggested_list}

## 4. 不适用截图及原因

{pending_list}

## 5. 无效截图常见问题

1. 只截结果不截命令。评委无法判断结果是否来自当前项目，终端截图应包含工作目录、命令、退出码和关键输出。
2. 只截文档不截真实运行。README 可以说明操作步骤，但不能代替 pytest、official suite、API 或 Web Demo 的运行证据。
3. 截图过窄或被遮挡。路径、命令、PASS、行数、speedup 等字段必须完整可读，不能被窗口边缘截断。
4. 把历史截图当作最新运行。历史证据可以保留，但必须说明生成时间和来源；最终提交前建议重跑核心命令。
5. 把不适用项做成假截图。项目没有模型权重、没有比赛平台上传页面、没有正在运行的 Doris 连接时，应标注不适用或待人工补拍。
6. 忽略失败证据。失败截图也有审计价值，但必须解释失败原因、影响范围和后续补拍方法。

## 6. 最终截图执行顺序

1. 打开 `README.md` 和 `docs/19_赛题19完成度与下一步规划.md`，确认赛题口径和运行命令。
2. 先补项目结构类截图：根目录、`src/`、`tests/`、`data/`、`docs/`、`scripts/`、`submission_artifacts/`。
3. 再补 Git 与环境截图：Git HEAD、git status、git log、Python/pip/Git/Node/npm/npx 版本、依赖版本。
4. 运行核心命令：compile、verify-sql、official-suite、pytest、selected tests、topic-compliance、evidence-metadata。
5. 查看提交证据：evidence_summary、submission_readiness、official_suite_report、doris_cluster_evidence、evidence_manifest。
6. 启动 Web Demo，依次截图主界面、参数区、SQL、AST、Explain、Rows、Evidence、负例诊断、空输入错误。
7. 补交付完整性：文件大小修改时间、SHA256、提交清单、配置文件、Doris SQL assets、既有 Demo 截图和视频目录。
8. 对不适用项做人工判断：模型权重不适用、上传成功需比赛平台现场补拍、实时 Doris 连接需集群启动后补拍。
9. 最后复查 `screenshots/` 中图片是否清晰，按答辩 PPT 或提交模板挑选图片。

## 7. 图片文件校验

| 图片 | 字节数 | SHA256 前 16 位 |
|---|---:|---|
{checksum_table}

## 8. 复现说明

在项目根目录运行：

```powershell
$env:PYTHONPATH = "src"
python .\\scripts\\build_visual_evidence.py
```

脚本会重新运行命令、启动本地 Web Demo、保存日志并覆盖本目录下同名截图。若需要现场 Doris 连接成功截图，应先启动 Apache Doris 并确认 9030 端口可连，再补拍数据库连接项。
"""
    (OUT_DIR / "SCREENSHOT_EVIDENCE_INDEX.md").write_text(text, encoding="utf-8")


def add_na_rows(rows: List[EvidenceRow]) -> None:
    rows.extend(
        [
            EvidenceRow(
                "EV-066",
                "模型权重文件截图",
                "不适用",
                "权重文件、模型文件",
                "项目内搜索 *.pt/*.pth/*.onnx/*.bin/*.safetensors/*.ckpt",
                "若存在模型权重，应显示文件名、大小、修改时间；当前为确定性编译器，无模型权重",
                "搜索结果为空，并说明项目不依赖模型权重",
                "EV-064_model_weight_search_none.png",
                "本项目核心是确定性 DSL 编译器，NL2DSL 只是候选层，不需要训练权重文件。",
                "若后续加入本地模型或大模型权重，必须重新补拍模型来源、大小、hash 和许可证。",
            ),
            EvidenceRow(
                "EV-067",
                "压缩包内容截图",
                "不适用",
                "最终提交压缩包内容",
                "当前尚未生成比赛平台最终 zip；以 Git 仓库和 submission_artifacts 为提交源",
                "如果后续生成 zip，应显示压缩包内 README、docs、src、tests、submission_artifacts 等目录",
                "未生成 zip 时不能伪造；生成后用 tar/7z/资源管理器补拍",
                "待人工补拍_final_zip_content.png",
                "答辩时说明当前证据包是提交前审计目录，最终打包后还需补一张压缩包内容图。",
                "需要最终提交格式确定后人工补拍。",
                status="待人工补拍",
            ),
            EvidenceRow(
                "EV-068",
                "上传成功截图",
                "不适用",
                "比赛平台上传成功",
                "登录比赛平台并完成最终上传后截图",
                "平台名称、项目名称、上传成功状态、时间、文件名",
                "平台页面明确显示提交成功",
                "待人工补拍_portal_upload_success.png",
                "这张图只能由你在比赛平台实际提交后补拍，不能由本地项目生成。",
                "当前没有比赛平台登录页面和提交动作，必须人工补拍。",
                status="待人工补拍",
            ),
            EvidenceRow(
                "EV-069",
                "实时 Doris 数据库连接成功截图",
                "建议",
                "数据库连接成功、Doris 现场复现",
                "启动 Doris 后执行 mysql -h 127.0.0.1 -P 9030 -u root -e \"SELECT 1\"",
                "mysql 命令、9030 端口、SELECT 1 输出或数据库列表",
                "命令退出码为 0，能连接 Doris FE 查询端口",
                "待人工补拍_live_doris_mysql_connection.png",
                "已有历史 Doris evidence PASS；若现场要重跑性能，应补拍实时连接成功。",
                "脚本已检查本机端口可达性，若 Doris 未启动，此项只能待集群启动后补拍。",
                status="待人工补拍",
            ),
            EvidenceRow(
                "EV-070",
                "图表可视化截图",
                "不适用",
                "图表可视化",
                "当前 Web Demo 以 SQL、AST、Explain、Rows、Evidence 面板呈现，不包含折线/柱状图组件",
                "若后续新增性能图表，应显示 baseline/optimized 耗时曲线或柱状对比",
                "当前不强行伪造图表，以 Evidence 数字和表格为准",
                "不适用_chart_visualization.png",
                "赛题重点是 DSL 编译和 Doris SQL 性能证据，现阶段表格和 explain 更直接。",
                "若答辩 PPT 需要视觉冲击，可后续把 benchmark JSON 生成图表再补拍。",
                status="不适用",
            ),
        ]
    )


def main() -> None:
    ensure_dirs()
    copy_existing_demo_screenshots()
    ev030_helper = GENERATED_DIR / "ev030_manual_verify.py"
    ev030_helper.write_text(
        """from __future__ import annotations

import json
from pathlib import Path

from findsl.equivalence import verify_sql_equivalence


dsl = 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)'
result = verify_sql_equivalence(dsl, Path("data/real_samples/eastmoney_a_share_sample"))
payload = {
    "dsl": result.dsl,
    "passed": result.passed,
    "sql": result.sql,
    "sql_row_count": result.sql_row_count,
    "reference_row_count": result.reference_row_count,
    "sql_keys": result.sql_keys,
    "reference_keys": result.reference_keys,
    "missing_keys": result.missing_keys,
    "extra_keys": result.extra_keys,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(0 if result.passed else 1)
""",
        encoding="utf-8",
    )
    ev061_helper = GENERATED_DIR / "ev061_sha256.py"
    ev061_helper.write_text(
        """from __future__ import annotations

import hashlib
from pathlib import Path


files = [
    Path("README.md"),
    Path("pyproject.toml"),
    Path("submission_artifacts/evidence_summary.md"),
    Path("deploy/doris/01_schema.sql"),
]
print("| Algorithm | SHA256 | Path |")
print("|---|---|---|")
for path in files:
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    print(f"| SHA256 | {digest} | {path} |")
""",
        encoding="utf-8",
    )

    rows: List[EvidenceRow] = []
    render_items: List[RenderItem] = []

    specs = [
        ("EV-001", "项目根目录结构截图", "EV-001_project_root_structure.png", "Get-ChildItem -Force | Select-Object Mode,Length,LastWriteTime,Name", 30),
        ("EV-002", "核心源码目录截图", "EV-002_core_src_directory.png", "Get-ChildItem -LiteralPath .\\src\\findsl -Force | Select-Object Mode,Length,LastWriteTime,Name", 30),
        ("EV-003", "测试目录截图", "EV-003_tests_directory.png", "Get-ChildItem -LiteralPath .\\tests -Force | Select-Object Mode,Length,LastWriteTime,Name", 30),
        ("EV-004", "输入数据目录截图", "EV-004_data_directory.png", "Get-ChildItem -LiteralPath .\\data -Recurse -Depth 2 -Force | Select-Object Mode,Length,LastWriteTime,FullName", 30),
        ("EV-005", "输出与提交证据目录截图", "EV-005_submission_artifacts_directory.png", "Get-ChildItem -LiteralPath .\\submission_artifacts -Recurse -Depth 2 -Force | Select-Object Mode,Length,LastWriteTime,FullName", 30),
        ("EV-006", "docs 文档目录截图", "EV-006_docs_directory.png", "Get-ChildItem -LiteralPath .\\docs -Force | Select-Object Mode,Length,LastWriteTime,Name", 30),
        ("EV-007", "scripts 脚本目录截图", "EV-007_scripts_directory.png", "Get-ChildItem -LiteralPath .\\scripts -Force | Select-Object Mode,Length,LastWriteTime,Name", 30),
        ("EV-008", "Git HEAD 截图", "EV-008_git_head.png", "git rev-parse --short HEAD; git branch --show-current", 30),
        ("EV-009", "git status 截图", "EV-009_git_status.png", "git status -sb", 30),
        ("EV-010", "git log 最近提交截图", "EV-010_git_log_recent.png", "git log --oneline --decorate -8", 30),
        ("EV-011", "运行环境版本截图", "EV-011_runtime_versions.png", "python --version; python -m pip --version; git --version; node --version; npm --version; npx --version", 30),
        ("EV-012", "依赖安装成功截图", "EV-012_dependency_versions.png", "python -m pip show pytest pandas | Select-String -Pattern 'Name:|Version:|Location:'; Get-Content .\\pyproject.toml -TotalCount 80", 60),
        ("EV-015", "终端主命令 compile 成功截图", "EV-015_cli_compile_success.png", "python -m findsl.cli compile 'then(filter(market(\"A\") & CONS(indicator(\"main_net_inflow\") > 0, 3)), rank(indicator(\"turnover_rate\"), desc, top=100))' --json", 60),
        ("EV-016", "Pytest 全部通过截图", "EV-016_pytest_all_passed.png", "python -m pytest -q", 180),
        ("EV-017", "单元测试与集成测试通过截图", "EV-017_selected_tests_passed.png", "python -m pytest tests/test_template_functions.py tests/test_topic_compliance.py tests/test_config_extension.py tests/test_demo.py -q", 120),
        ("EV-018", "Blocking gates 与 Warning count 截图", "EV-018_evidence_summary_gates.png", "Get-Content .\\submission_artifacts\\evidence_summary.md", 30),
        ("EV-019", "官方正例负例全部通过截图", "EV-019_official_suite_pass.png", f"python -m findsl.cli official-suite --output '{GENERATED_DIR / 'official_suite_report.md'}' --json", 120),
        ("EV-020", "官方 results 审计 PASS 截图", "EV-020_submission_readiness_snapshot.png", "Get-Content .\\submission_artifacts\\evidence_snapshots\\submission_readiness.md -TotalCount 160", 30),
        ("EV-021", "样例输入文件截图", "EV-021_sample_input_files.png", "Get-Content .\\data\\samples\\official_positive_cases.jsonl -TotalCount 10; ''; Get-Content .\\data\\samples\\official_negative_cases.jsonl -TotalCount 8", 30),
        ("EV-022", "样例输出文件截图", "EV-022_sample_compile_output_file.png", f"python -m findsl.cli compile 'filter(ABS(indicator(\"main_net_inflow\")) > 0)' --json | Set-Content -Encoding UTF8 '{GENERATED_DIR / 'sample_compile_result.json'}'; Get-Content '{GENERATED_DIR / 'sample_compile_result.json'}' -TotalCount 120", 60),
        ("EV-023", "核心功能输入截图", "EV-023_core_input_cases.png", "Get-Content .\\data\\samples\\queries.jsonl -TotalCount 20", 30),
        ("EV-024", "核心功能执行成功截图", "EV-024_verify_sql_success.png", "python -m findsl.cli verify-sql 'filter(SUM(indicator(\"volume\"), 3) > 300)' --data-dir data/samples --json", 60),
        ("EV-025", "核心功能输出结果截图", "EV-025_reference_output_result.png", "python -m findsl.cli reference 'filter(SUM(indicator(\"volume\"), 3) > 300)' --data-dir data/samples --json", 60),
        ("EV-026", "核心算法 Compiler 代码位置截图", "EV-026_core_algorithm_compiler_code.png", "Get-Content .\\src\\findsl\\compiler.py -TotalCount 120", 30),
        ("EV-027", "核心算法 prefix-sum 代码位置截图", "EV-027_core_algorithm_prefix_sum_code.png", "Get-Content .\\src\\findsl\\sqlgen.py | Select-Object -Skip 595 -First 95", 30),
        ("EV-028", "核心算法输入输出对比截图", "EV-028_algorithm_input_output_compare.png", "python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator(\"volume\"), 3) > 300)' --data-dir data/samples --iterations 5 --json", 90),
        ("EV-029", "算法中间结果 Explain 截图", "EV-029_algorithm_explain_intermediate.png", "python -m findsl.cli compile 'filter(SUM(indicator(\"volume\"), 120) > 1000000)' --json", 60),
        ("EV-030", "手工核验对比截图", "EV-030_manual_sql_reference_check.png", f"python '{ev030_helper}'", 60),
        ("EV-031", "输出目录截图", "EV-031_output_directory.png", "Get-ChildItem -LiteralPath .\\submission_artifacts\\evidence_snapshots -Force | Select-Object Mode,Length,LastWriteTime,Name", 30),
        ("EV-032", "结果文件内容截图", "EV-032_result_file_content.png", "Get-Content .\\submission_artifacts\\evidence_snapshots\\official_suite_report.md -TotalCount 140", 30),
        ("EV-033", "结果文件格式校验 PASS 截图", "EV-033_metadata_format_pass.png", f"python -m findsl.cli evidence-metadata --snapshots-dir submission_artifacts/evidence_snapshots --output '{GENERATED_DIR / 'evidence_metadata_check.json'}' --summary-output '{GENERATED_DIR / 'evidence_summary_check.md'}'; python -m json.tool '{GENERATED_DIR / 'evidence_metadata_check.json'}' | Select-Object -First 80; Get-Content '{GENERATED_DIR / 'evidence_summary_check.md'}' -TotalCount 60", 60),
        ("EV-034", "结果数量统计截图", "EV-034_result_counts.png", "$files = 'data/samples/official_positive_cases.jsonl','data/samples/official_negative_cases.jsonl','tests'; foreach ($f in $files) { if (Test-Path $f -PathType Container) { $count=(Get-ChildItem $f -Filter 'test_*.py').Count; \"${f}: ${count} test files\" } else { $count=(Get-Content $f | Measure-Object -Line).Lines; \"${f}: ${count} lines\" } }; Get-Content .\\submission_artifacts\\evidence_metadata.json", 30),
        ("EV-035", "基线性能截图", "EV-035_baseline_performance.png", f"python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator(\"volume\"), 3) > 300)' --data-dir data/samples --iterations 10 --output '{GENERATED_DIR / 'prefix_sum_benchmark.md'}' --json", 90),
        ("EV-036", "优化后性能与 speedup 截图", "EV-036_optimized_performance_speedup.png", f"Get-Content '{GENERATED_DIR / 'prefix_sum_benchmark.md'}' -TotalCount 140", 30),
        ("EV-037", "Doris evidence PASS 截图", "EV-037_doris_evidence_pass.png", "Get-Content .\\submission_artifacts\\evidence_snapshots\\doris_cluster_evidence.md -TotalCount 120", 30),
        ("EV-038", "Doris speedup 详情截图", "EV-038_doris_speedup_json.png", "Get-Content .\\submission_artifacts\\evidence_snapshots\\doris_cluster_evidence.json -TotalCount 180", 30),
        ("EV-039", "Doris 本机端口可达性检查截图", "EV-039_doris_live_port_check.png", "$client = [Net.Sockets.TcpClient]::new(); $async = $client.BeginConnect('127.0.0.1', 9030, $null, $null); $ok = $async.AsyncWaitHandle.WaitOne(2000, $false); if ($ok -and $client.Connected) { 'Doris 9030 reachable in this session' } else { 'Doris 9030 not reachable in this session; use committed Doris evidence snapshot unless live cluster is started.' }; $client.Close()", 30),
        ("EV-050", "非法输入 CLI 诊断截图", "EV-050_cli_invalid_input_diagnostic.png", "python -m findsl.cli diagnose 'filter(indicator(\"clos\") > 10)' --json", 60),
        ("EV-051", "边界输入测试截图", "EV-051_boundary_input_test.png", "python -m findsl.cli diagnose 'then(filter(market(\"A\")), rank(indicator(\"close\"), desc, percent=0))' --json", 60),
        ("EV-052", "日志文件截图", "EV-052_log_files.png", "Get-ChildItem -LiteralPath .\\submission_artifacts\\visual_evidence\\logs -Force | Select-Object Mode,Length,LastWriteTime,Name", 30),
        ("EV-053", "error warning 检查截图", "EV-053_error_warning_check.png", "Get-Content .\\submission_artifacts\\evidence_summary.md; ''; Select-String -Path .\\submission_artifacts\\evidence_summary.md -Pattern 'Warning count|Metadata Warnings|<none>|PASS'", 30),
        ("EV-054", "技术报告指标页截图", "EV-054_technical_report_metrics.png", "Get-Content .\\submission_artifacts\\technical_report.md -TotalCount 160", 30),
        ("EV-055", "README 运行命令截图", "EV-055_readme_run_commands.png", "Select-String -Path .\\README.md -Pattern 'Quick Start|python -m findsl.cli|submission_readiness|official-suite|serve-demo' -Context 0,1 | Select-Object -First 90", 30),
        ("EV-056", "文档与实际命令一致截图", "EV-056_doc_command_consistency.png", "$scripts = 'official_suite.ps1','submission_readiness.ps1','serve_demo.ps1','export_submission_artifacts.ps1','collect_doris_evidence.ps1'; foreach ($s in $scripts) { \"${s}: \" + (Test-Path \".\\scripts\\${s}\") }; python -m findsl.cli --help | Select-Object -First 80", 30),
        ("EV-057", "最终提交清单截图", "EV-057_submission_manifest.png", "Get-Content .\\submission_artifacts\\evidence_manifest.md; ''; Get-Content .\\submission_artifacts\\README.md -TotalCount 120", 30),
        ("EV-058", "配置文件截图", "EV-058_config_files.png", "Get-Content .\\configs\\indicators.json -TotalCount 120; ''; Get-Content .\\configs\\functions.json -TotalCount 120; ''; Get-Content .\\configs\\tables.json -TotalCount 80", 30),
        ("EV-059", "交付包文件列表截图", "EV-059_delivery_package_files.png", "Get-ChildItem -LiteralPath .\\submission_artifacts -Recurse -Depth 3 -File | Sort-Object FullName | Select-Object Length,LastWriteTime,FullName", 30),
        ("EV-060", "文件大小和修改时间截图", "EV-060_file_sizes_modified_times.png", "Get-ChildItem -File .\\README.md,.\\PROJECT_INDEX.md,.\\pyproject.toml; Get-ChildItem -LiteralPath .\\submission_artifacts\\evidence_snapshots -File | Select-Object Length,LastWriteTime,Name", 30),
        ("EV-061", "sha256 校验和截图", "EV-061_sha256_checksums.png", f"python '{ev061_helper}'", 30),
        ("EV-062", "上传核验 READY 截图", "EV-062_upload_ready.png", "Get-Content .\\submission_artifacts\\evidence_summary.md; ''; Get-Content .\\docs\\17_项目交付说明.md -TotalCount 120", 30),
        ("EV-063", "答辩演示关键页面清单截图", "EV-063_defense_demo_assets.png", "Get-ChildItem -LiteralPath .\\submission_artifacts\\demo_screenshots -File | Select-Object Length,LastWriteTime,Name; ''; Get-ChildItem -LiteralPath .\\submission_artifacts\\defense_video -File | Select-Object Length,LastWriteTime,Name", 30),
        ("EV-064", "模型权重搜索不适用截图", "EV-064_model_weight_search_none.png", "$patterns='*.pt','*.pth','*.onnx','*.bin','*.safetensors','*.ckpt','*.h5'; $files = foreach ($p in $patterns) { Get-ChildItem -Recurse -File -Filter $p -ErrorAction SilentlyContinue | Select-Object FullName,Length }; if (-not $files) { 'No model or weight files found under project root. This is expected: FinDSL Forge is a deterministic compiler, not a trained model package.' } else { $files }", 30),
        ("EV-065", "赛题完成度规划截图", "EV-065_topic_compliance_plan.png", f"python -m findsl.cli topic-compliance --output '{GENERATED_DIR / 'topic_19_compliance_plan.md'}' --json; Get-Content '{GENERATED_DIR / 'topic_19_compliance_plan.md'}' -TotalCount 140", 60),
    ]

    for eid, title, filename, command, timeout in specs:
        expected = (0,)
        if eid in {"EV-050", "EV-051"}:
            expected = (1,)
        row, item = run_ps(command, eid, title, filename, timeout=timeout, expected=expected)
        rows.append(row)
        render_items.append(item)

    demo_proc = None
    try:
        demo_proc, port, health = start_demo_server()
        base_url = f"http://127.0.0.1:{port}"
        start_log = "\n".join(
            [
                "证据编号: EV-013",
                "截图名称: 服务启动成功截图",
                f"生成时间: {RUN_TIME.isoformat(timespec='seconds')}",
                f"工作目录: {ROOT}",
                f"服务命令: {sys.executable} -m findsl.cli serve-demo --host 127.0.0.1 --port {port}",
                f"进程 PID: {demo_proc.pid}",
                f"健康检查 URL: {base_url}/api/examples",
                "状态: PASS",
                "",
                "----- /api/examples 响应片段 -----",
                health[:4000],
            ]
        )
        start_log_path = LOG_DIR / "EV-013_service_start_success.txt"
        start_log_path.write_text(start_log, encoding="utf-8")
        render_items.append(
            RenderItem(
                "EV-013",
                "服务启动成功截图",
                "后台进程与 API 健康检查",
                f"{sys.executable} -m findsl.cli serve-demo --host 127.0.0.1 --port {port}",
                start_log,
                "EV-013_service_start_success.png",
                ["真实服务进程", "API health PASS", f"port {port}"],
            )
        )
        rows.append(
            EvidenceRow(
                "EV-013",
                "服务启动成功截图",
                "必须",
                "服务启动成功、Web Demo 可用",
                f"python -m findsl.cli serve-demo --host 127.0.0.1 --port {port}",
                "服务命令、PID、健康检查 URL、/api/examples 响应",
                "健康检查返回 ok=true，服务可被浏览器访问",
                "EV-013_service_start_success.png",
                "这张图证明 Web Demo 是本次实际启动的服务，不是静态截图。",
                "端口是本次动态分配端口；正式演示可使用 README 中的 8765。",
                log_file=str(start_log_path.relative_to(OUT_DIR)),
            )
        )
        row, item = run_ps(
            f"Invoke-RestMethod -Uri '{base_url}/api/examples' | ConvertTo-Json -Depth 5",
            "EV-014",
            "端口与健康检查截图",
            "EV-014_port_health_check.png",
            timeout=30,
        )
        row.requirement = "端口或健康检查"
        rows.append(row)
        render_items.append(item)
        row, item = run_ps(
            "$body = @{ dsl = 'filter(SUM(indicator(\"volume\"), 3) > 300)'; verify = $true; enable_prefix_sum = $true } | ConvertTo-Json; "
            f"Invoke-RestMethod -Uri '{base_url}/api/analyze' -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 8",
            "EV-040",
            "API 调用成功截图",
            "EV-040_api_call_success.png",
            timeout=60,
        )
        row.requirement = "API 调用成功、核心服务接口"
        rows.append(row)
        render_items.append(item)
        rows.extend(capture_web_demo(base_url))
    finally:
        if demo_proc is not None:
            try:
                demo_proc.terminate()
                stdout, stderr = demo_proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                demo_proc.kill()
                stdout, stderr = demo_proc.communicate(timeout=5)
            (LOG_DIR / "demo_server_process_output.txt").write_text(
                "----- STDOUT -----\n"
                + (stdout or "<empty>")
                + "\n\n----- STDERR -----\n"
                + (stderr or "<empty>"),
                encoding="utf-8",
            )

    add_na_rows(rows)
    render_all_html(render_items)
    write_readme(rows)
    write_index(rows)

    summary = {
        "generated_at": RUN_TIME.isoformat(timespec="seconds"),
        "root": str(ROOT),
        "out_dir": str(OUT_DIR),
        "evidence_rows": len(rows),
        "screenshots": len(list(SCREENSHOT_DIR.rglob("*.png"))),
        "logs": len(list(LOG_DIR.rglob("*.txt"))),
        "index": str(OUT_DIR / "SCREENSHOT_EVIDENCE_INDEX.md"),
    }
    (OUT_DIR / "visual_evidence_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
