"""Compliance memo rendering.

Two output targets:
  * Markdown (`build_memo_md`) — one memo file per scenario (offline demo).
  * Self-contained HTML (`build_report_html` / `write_report_html`) — a
    zero-dependency, offline, CDN-free dashboard with the 🟢🟡🔴 verification
    matrix, summary KPIs, per-law breakdown, scenario tabs, and an optional
    live-verify section. Opened directly in a browser (double-click) or served
    by ``compliance_triangle.web``.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

_STATUS_LABEL = {
    "OK": "已核验通过",
    "NOT_FOUND": "条文不存在/未生效",
    "TEMPORAL_DEPRECATED": "引用已废止法律",
    "PARTIAL": "引述差异(待复核)",
    "FABRICATED": "引述不符(待复核)",
    "UNVERIFIABLE": "未核验节点",
}

# --- CSS (offline, no external resources) ----------------------------------- #
_CSS = """
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,Roboto,sans-serif;
       background:#f1f5f9; color:#0f172a; line-height:1.5; }
.wrap { max-width:1000px; margin:0 auto; padding:0 20px; }
.hero { background:linear-gradient(135deg,#4f46e5,#7c3aed); color:#fff; padding:40px 0 30px; }
.hero h1 { margin:0 0 8px; font-size:30px; }
.hero .sub { font-size:16px; opacity:.8; font-weight:400; margin-left:8px; }
.hero .tag { margin:0 0 6px; font-size:15px; opacity:.95; }
.hero .meta { margin:0; font-size:13px; opacity:.85; }
.hero b { font-weight:700; }
.block { background:#fff; border-radius:14px; padding:22px 24px; margin:22px 0;
         box-shadow:0 1px 3px rgba(0,0,0,.08); }
.block h2 { margin:0 0 16px; font-size:20px; }
.kpis { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:18px; }
.kpi { flex:1; min-width:120px; background:#f8fafc; border:1px solid #e2e8f0;
       border-radius:12px; padding:14px; text-align:center; }
.kpi .n { font-size:30px; font-weight:700; }
.kpi.g .n { color:#16a34a; } .kpi.y .n { color:#d97706; } .kpi.r .n { color:#dc2626; }
.bars { display:flex; flex-direction:column; gap:10px; margin-bottom:18px; }
.bar .blabel { display:flex; justify-content:space-between; font-size:13px;
               margin-bottom:4px; color:#334155; }
.track { background:#e2e8f0; border-radius:8px; height:14px; overflow:hidden; }
.fill { height:100%; border-radius:8px; }
.fill.g { background:#16a34a; } .fill.y { background:#d97706; } .fill.r { background:#dc2626; }
.lawbreak h3 { font-size:15px; margin:6px 0 10px; }
.lawrow { display:flex; align-items:center; gap:12px; padding:6px 0;
          border-bottom:1px solid #f1f5f9; font-size:14px; }
.lawrow .lname { flex:1; font-weight:600; }
.lawrow .lc { font-variant-numeric:tabular-nums; }
.lc.g { color:#16a34a; } .lc.y { color:#d97706; } .lc.r { color:#dc2626; }
.tabs { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
.tab { border:1px solid #c7d2fe; background:#eef2ff; color:#4338ca; padding:8px 14px;
       border-radius:999px; cursor:pointer; font-size:14px; }
.tab.active { background:#4f46e5; color:#fff; border-color:#4f46e5; }
.panes .pane { display:none; }
.panes .pane.show { display:block; }
.metarow { display:flex; align-items:center; gap:10px; flex-wrap:wrap;
           margin-bottom:12px; font-size:13px; color:#475569; }
.pill { padding:2px 8px; border-radius:999px; font-weight:600; }
.pill.g { background:#dcfce7; color:#16a34a; } .pill.y { background:#fef3c7; color:#d97706; }
.pill.r { background:#fee2e2; color:#dc2626; }
.overall { margin-left:auto; font-weight:700; color:#0f172a; }
.scenario-desc { background:#f8fafc; border-left:3px solid #4f46e5; padding:10px 14px;
                 border-radius:0 8px 8px 0; margin-bottom:12px; font-size:14px; }
.raw { margin-bottom:14px; } .raw summary { cursor:pointer; color:#4f46e5; font-size:14px; }
.raw pre { white-space:pre-wrap; background:#0f172a; color:#e2e8f0; padding:14px;
            border-radius:10px; font-size:13px; overflow:auto; }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:12px; }
.card { border-radius:12px; padding:14px; border:1px solid; background:#fff; }
.card.g { border-color:#86efac; background:#f0fdf4; }
.card.y { border-color:#fcd34d; background:#fffbeb; }
.card.r { border-color:#fca5a5; background:#fef2f2; }
.card .ctop { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.card .bdg { font-size:18px; }
.card .cit { font-weight:700; font-size:15px; }
.card .st { font-size:13px; font-weight:600; margin-bottom:4px; }
.card .note { font-size:13px; color:#334155; }
.card .lbl { font-size:12px; color:#64748b; font-weight:600; }
.card .qtxt, .card .gtxt { font-size:12.5px; background:#fff; border:1px solid #e2e8f0;
            border-radius:8px; padding:8px; margin-top:4px; max-height:160px; overflow:auto; }
.card .gtxt { color:#0f172a; }
.qt, .gt { margin-top:8px; }
.live-controls { display:flex; align-items:center; gap:14px; margin:12px 0; flex-wrap:wrap; }
.live-controls label { font-size:14px; color:#334155; }
.live-controls input[type=date] { padding:6px 8px; border:1px solid #cbd5e1; border-radius:8px; }
.run { background:#4f46e5; color:#fff; border:none; padding:9px 18px; border-radius:10px;
       cursor:pointer; font-size:14px; font-weight:600; }
.run:hover { background:#4338ca; }
#answer, #scenario { width:100%; min-height:140px; border:1px solid #cbd5e1; border-radius:10px;
          padding:12px; font-size:14px; font-family:inherit; resize:vertical; }
#scenario { min-height:80px; margin-bottom:10px; }
.liveOut { margin-top:16px; }
.liveOut.show { display:block; }
.loading, .err { padding:16px; border-radius:10px; font-size:14px; }
.loading { background:#eef2ff; color:#4338ca; }
.err { background:#fee2e2; color:#dc2626; }
.footnote p { font-size:13px; color:#475569; margin:6px 0; }
.footnote .src { margin-top:12px; padding-top:12px; border-top:1px solid #e2e8f0; color:#64748b; }
.notice { background:#fffbeb; border:1px solid #fcd34d; color:#92400e; padding:10px 14px;
          border-radius:10px; font-size:13px; margin:10px 0 0; }
.caveats { margin:10px 0 0; padding:10px 14px; background:#f8fafc; border:1px solid #e2e8f0;
           border-radius:10px; }
.caveats b { color:#334155; }
.caveats ul { margin:6px 0 0; padding-left:20px; }
.caveats li { font-size:13px; color:#64748b; margin:3px 0; }
code { background:#f1f5f9; padding:2px 6px; border-radius:6px; font-size:12px; }
.hint { font-size:14px; color:#475569; margin:0 0 6px; }
"""

# --- JS (vanilla, offline) ------------------------------------------------- #
_JS = """
const DATA = __DATA_JSON__;
const WITH_LIVE = __WITH_LIVE__;
function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function badgeKey(b){ return b==='🟢'?'g':b==='🟡'?'y':'r'; }
function statusLabel(s){ var m={'OK':'已核验通过','NOT_FOUND':'条文不存在/未生效',
  'TEMPORAL_DEPRECATED':'引用已废止法律','PARTIAL':'引述差异(待复核)',
  'FABRICATED':'引述不符(待复核)','UNVERIFIABLE':'未核验节点'}; return m[s]||s; }

function bar(label,n,p,k){ return '<div class="bar"><div class="blabel"><span>'+label+
  '</span><span>'+n+' ('+p+'%)</span></div><div class="track"><div class="fill '+k+
  '" style="width:'+p+'%"></div></div></div>'; }

function renderSummary(){
  var g=0,y=0,r=0; var law={};
  DATA.forEach(function(d){ var c=d.result.counts; g+=c['🟢']||0; y+=c['🟡']||0; r+=c['🔴']||0;
    d.result.items.forEach(function(it){ var k=it.raw_law; if(!law[k]) law[k]={g:0,y:0,r:0};
      law[k][badgeKey(it.badge)]++; }); });
  var total=g+y+r; var pct=function(n){ return total?Math.round(n/total*100):0; };
  var bars=bar('🟢 已核验通过',g,pct(g),'g')+bar('🟡 待人工复核',y,pct(y),'y')+
           bar('🔴 未通过核验',r,pct(r),'r');
  var lawRows='';
  Object.keys(law).sort().forEach(function(k){ var L=law[k];
    lawRows+='<div class="lawrow"><span class="lname">'+esc(k)+'</span>'+
      '<span class="lc g">🟢'+L.g+'</span><span class="lc y">🟡'+L.y+
      '</span><span class="lc r">🔴'+L.r+'</span></div>'; });
  document.getElementById('dash').innerHTML=
    '<div class="kpis"><div class="kpi g"><div class="n">'+g+'</div><div>🟢 通过</div></div>'+
    '<div class="kpi y"><div class="n">'+y+'</div><div>🟡 待复核</div></div>'+
    '<div class="kpi r"><div class="n">'+r+'</div><div>🔴 未通过</div></div>'+
    '<div class="kpi"><div class="n">'+total+'</div><div>引注总数</div></div></div>'+
    '<div class="bars">'+bars+'</div><div class="lawbreak"><h3>按法律分布</h3>'+lawRows+'</div>';
}

function cardHtml(it){
  var bc=badgeKey(it.badge); var extra=''; var q='';
  if(it.ground_truth){ extra='<div class="gt"><span class="lbl">官方原文</span>'+
    '<div class="gtxt">'+esc(it.ground_truth)+'</div></div>'; }
  if(it.quoted){ q='<div class="qt"><span class="lbl">AI 引述</span>'+
    '<div class="qtxt">'+esc(it.quoted)+'</div></div>'; }
  return '<div class="card '+bc+'"><div class="ctop"><span class="bdg">'+it.badge+
    '</span><span class="cit">《'+esc(it.raw_law)+'》第'+esc(it.article_no)+'条</span></div>'+
    '<div class="st">'+statusLabel(it.status)+'</div><div class="note">'+esc(it.note)+
    '</div>'+q+extra+'</div>';
}

function renderScenarios(){
  var tabs='', bodies='';
  DATA.forEach(function(d,i){ var active=i===0?' active':'';
    tabs+='<button class="tab'+active+'" data-i="'+i+'">'+esc(d.scenario.title)+'</button>';
    var cards=d.result.items.map(cardHtml).join(''); var c=d.result.counts;
    bodies+='<div class="pane'+(i===0?' show':'')+'" data-i="'+i+'">'+
      '<div class="metarow"><span>基准日 '+esc(d.result.as_of)+'</span>'+
      '<span class="pill g">🟢'+c['🟢']+'</span><span class="pill y">🟡'+c['🟡']+
      '</span><span class="pill r">🔴'+c['🔴']+'</span>'+
      '<span class="overall">'+esc(d.result.overall)+'</span></div>'+
      '<div class="scenario-desc">'+esc(d.scenario.scenario)+'</div>'+
      '<details class="raw"><summary>AI 合规分析（原始输出）</summary><pre>'+esc(d.answer)+
      '</pre></details><div class="cards">'+cards+'</div></div>'; });
  document.getElementById('tabs').innerHTML=tabs;
  document.getElementById('panes').innerHTML=bodies;
  document.querySelectorAll('.tab').forEach(function(b){ b.addEventListener('click',function(){
    var i=b.getAttribute('data-i');
    document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('active');});
    document.querySelectorAll('.pane').forEach(function(x){x.classList.remove('show');});
    b.classList.add('active'); document.querySelector('.pane[data-i="'+i+'"]').classList.add('show');
  }); });
}

function renderResult(res){
  var c=res.counts; var cards=res.items.map(cardHtml).join('');
  document.getElementById('liveOut').innerHTML=
    '<div class="metarow"><span>基准日 '+esc(res.as_of)+'</span>'+
    '<span class="pill g">🟢'+c['🟢']+'</span><span class="pill y">🟡'+c['🟡']+
    '</span><span class="pill r">🔴'+c['🔴']+'</span><span class="overall">'+esc(res.overall)+
    '</span></div><div class="cards">'+cards+'</div>';
  document.getElementById('liveOut').classList.add('show');
}

function runVerify(){
  var ans=document.getElementById('answer').value;
  var asof=document.getElementById('as_of').value||'2026-08-01';
  if(!ans.trim()){ alert('请先粘贴一段 AI 生成的合规分析（含《法律》第X条引注）'); return; }
  document.getElementById('liveOut').innerHTML='<div class="loading">校验中…</div>';
  fetch('/verify',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({answer:ans,as_of_date:asof})})
    .then(function(r){return r.json();})
    .then(function(d){ if(d.error){ document.getElementById('liveOut').innerHTML=
      '<div class="err">'+esc(d.error)+'</div>'; } else { renderResult(d); } })
    .catch(function(e){ document.getElementById('liveOut').innerHTML=
      '<div class="err">校验失败：'+esc(e)+'（需启动本地服务 python -m compliance_triangle.web）</div>'; });
}

function runModelVerify(){
  var sc=document.getElementById('scenario');
  if(!sc){ alert('本页面未启用实时模型（仅粘贴模式）。'); return; }
  var scenario=sc.value;
  var model=document.getElementById('model')?document.getElementById('model').value:'';
  var asof=document.getElementById('as_of').value||'2026-08-01';
  if(!scenario.trim()){ alert('请先填写合规场景'); return; }
  document.getElementById('liveOut').innerHTML='<div class="loading">模型生成中…</div>';
  fetch('/analyze',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({scenario:scenario,as_of_date:asof,model:model})})
    .then(function(r){return r.json();})
    .then(function(d){ if(d.error){ document.getElementById('liveOut').innerHTML=
      '<div class="err">'+esc(d.error)+'</div>'; }
      else { if(d.answer){ document.getElementById('answer').value=d.answer; }
             renderResult(d.result); } })
    .catch(function(e){ document.getElementById('liveOut').innerHTML=
      '<div class="err">调用失败：'+esc(e)+'</div>'; });
}

document.addEventListener('DOMContentLoaded',function(){
  renderSummary(); renderScenarios();
  if(WITH_LIVE){
    var rb=document.getElementById('runBtn'); if(rb){ rb.addEventListener('click',runVerify); }
    var rmb=document.getElementById('runModelBtn'); if(rmb){ rmb.addEventListener('click',runModelVerify); }
  }
});
"""

_LIVE_SECTION_TPL = """
<section class="block live">
  <h2>实时校验 · 让 AI 分析你的合规场景</h2>
  <p class="hint">两种用法：① 填写场景 + 选择模型，点击「调用模型并校验」由系统调用国产大模型生成分析并自动逐条核验；② 直接粘贴任意 LLM 生成的合规分析（含《法律》第X条引注）到下方，点击「运行校验（粘贴模式）」。</p>
  {note}
  <div class="live-controls">
    <label>分析基准日 <input id="as_of" type="date" value="2026-08-01"></label>
    {model_select}
    {model_btn}
    <button id="runBtn" class="run">运行校验（粘贴模式）</button>
  </div>
  <textarea id="scenario" placeholder="填写合规场景，例如：公司拟为关联方提供大额保证担保，需确认决议程序与违约救济……"></textarea>
  <textarea id="answer" placeholder="或在此粘贴 AI 生成的合规分析（含《法律名称》第X条引注），例如：依据《公司法》第142条……《个人所得税法》第2条……《旧公司法》第16条……"></textarea>
  <div id="liveOut" class="liveOut"></div>
</section>
"""


def _build_live_section(live_models) -> str:
    """Render the live section. With models available: show a model picker +
    a 'call model' button. Without: paste-only mode + a clear notice."""
    if live_models:
        opts = "".join(f'<option value="{m}">{m}</option>' for m in live_models)
        model_select = f'<label>模型 <select id="model">{opts}</select></label>'
        model_btn = '<button id="runModelBtn" class="run">调用模型并校验</button>'
        note = ""
    else:
        model_select = ""
        model_btn = ""
        note = ('<p class="notice">⚠️ 未检测到任何模型 API key（环境变量），实时调用模型已禁用。'
                '可粘贴 AI 输出进行核验，或在环境中配置 DEEPSEEK_API_KEY 等后重启服务以启用实时模式。</p>')
    return _LIVE_SECTION_TPL.format(note=note, model_select=model_select,
                                    model_btn=model_btn)

_TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<header class="hero"><div class="wrap">
  <h1>合规三角 <span class="sub">Compliance Triangle</span></h1>
  <p class="tag">法律合规 · 税务合规 · 知识产权合规 —— 同一套 verify 引擎，为 AI 生成的每条法条引注把关</p>
  <p class="meta">基准库：<b>__KB_ARTICLES__</b> 条已核验法条（<b>__KB_LAWS__</b> 部法，源自 legal-hallucination-bench）｜ 引注核验：🟢通过 🟡待复核 🔴未通过</p>
  __NOTICE__
</div></header>
<main class="wrap">
  <section class="block"><h2>核验总览</h2><div id="dash"></div></section>
  <section class="block">
    <h2>演示场景（内置 5 个含幻觉样本）</h2>
    <div id="tabs" class="tabs"></div>
    <div id="panes" class="panes"></div>
  </section>
  __LIVE_SECTION__
  <section class="block footnote">
    <p>🟢 <b>已核验通过</b>：法条存在且在有效期内（仅作存在性核验，未提供引述文本做逐字比对；或引述与官方原文逐字一致）。</p>
    <p>🟡 <b>待人工复核</b>：法条真实存在，但 AI 引述的措辞/但书与官方原文不一致，请人工比对。</p>
    <p>🔴 <b>未通过核验</b>：条文不存在/未生效，或引用了已废止法律——相关合规结论不可轻信。</p>
    <p class="src">本产品复用 <code>legal-hallucination-bench</code> 的 verify 引擎（同一套严格逐字内容策略），锚定 2327 条已核验法条全文。AI 可能编造法条，本系统负责拦截。</p>
  __CAVEATS__
  </section>
</main>
<script>__JS__</script>
</body>
</html>
"""


# --- Markdown (one memo per scenario) -------------------------------------- #
def build_memo_md(scenario: Dict, answer: str, result: Dict) -> str:
    """Render a compliance memo (Markdown) with the 🟢🟡🔴 verification matrix."""
    title = scenario.get("title", scenario.get("id", "场景"))
    as_of = result["as_of"]
    c = result["counts"]
    lines = []
    lines.append(f"# 合规备忘录 · {title}")
    lines.append("")
    lines.append(f"- **分析基准日**：{as_of}")
    lines.append(f"- **整体结论**：{result['overall']}")
    lines.append(f"- **引注核验统计**：🟢 {c['🟢']} · 🟡 {c['🟡']} · 🔴 {c['🔴']}")
    lines.append("")
    lines.append("## 一、场景")
    lines.append("")
    lines.append(scenario.get("scenario", ""))
    lines.append("")
    lines.append("## 二、AI 合规分析（原始输出）")
    lines.append("")
    lines.append("```text")
    lines.append(answer.strip())
    lines.append("```")
    lines.append("")
    lines.append("## 三、引注核验矩阵")
    lines.append("")
    lines.append("| 徽章 | 引注 | 核验状态 | 诊断说明 |")
    lines.append("| --- | --- | --- | --- |")
    for it in result["items"]:
        cit = f"《{it['raw_law']}》第{it['article_no']}条"
        status = _STATUS_LABEL.get(it["status"], it["status"])
        note = it["note"].replace("|", "／")
        lines.append(f"| {it['badge']} | {cit} | {status} | {note} |")
    lines.append("")
    lines.append("## 四、结论与建议")
    lines.append("")
    if c["🔴"]:
        lines.append("- 🔴 **存在未通过核验的引注**：上述标红条目要么条文不存在/未生效，"
                     "要么引用了已废止法律。相关合规结论**不可轻信**，须由人工核实真实条文后再采纳。")
    if c["🟡"]:
        lines.append("- 🟡 **存在引述差异**：标黄条目对应真实条文，但 AI 引述的措辞/但书与官方原文不一致，"
                     "建议人工比对官方文本后使用。")
    if not c["🔴"] and not c["🟡"]:
        lines.append("- 🟢 全部引注通过存在性与时效性核验，可作为进一步人工复核的基础。")
    lines.append("")
    lines.append("> 本备忘录的引注核验复用 `legal-hallucination-bench` 的 verify 引擎，"
                 "锚定 2327 条已核验法条全文。AI 可能编造法条，本系统负责拦截。")
    lines.append("")
    return "\n".join(lines)


# --- Self-contained HTML report -------------------------------------------- #
def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_report_html(data: List[Dict], with_live: bool = True,
                       kb_laws: Optional[int] = None,
                       kb_articles: Optional[int] = None,
                       notice: Optional[str] = None,
                       caveats: Optional[List[str]] = None,
                       live_models: Optional[List[str]] = None) -> str:
    """Build a self-contained, offline HTML report from ``data`` (list of
    ``{"scenario", "answer", "result"}``). No CDN/external resources.

    ``kb_laws`` / ``kb_articles`` : honest KB size for the hero banner.
    ``notice``  : an amber banner (e.g. KB not loaded) shown under the hero.
    ``caveats`` : a list of honest data-coverage caveats shown in the footnote.
    ``live_models`` : wired model labels (API key present). When non-empty, the
        live section shows a model picker + 'call model' button; when empty/None
        it falls back to paste-only mode with a clear notice.
    """
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    if with_live:
        live_section = _build_live_section(live_models or [])
    else:
        live_section = ""
    notice_html = (f'<p class="notice">⚠️ {_esc(notice)}</p>' if notice else "")
    caveats_html = ""
    if caveats:
        items = "".join(f"<li>{_esc(c)}</li>" for c in caveats)
        caveats_html = (
            '<div class="caveats"><b>数据覆盖说明（诚实披露）：</b>'
            f'<ul>{items}</ul></div>'
        )
    html = _TPL
    html = html.replace("__TITLE__", "合规三角 · 引注核验演示")
    html = html.replace("__CSS__", _CSS)
    html = html.replace("__JS__", _JS)
    html = html.replace("__DATA_JSON__", data_json)
    html = html.replace("__WITH_LIVE__", "true" if with_live else "false")
    html = html.replace("__KB_LAWS__", str(kb_laws if kb_laws is not None else ""))
    html = html.replace("__KB_ARTICLES__", str(kb_articles if kb_articles is not None else ""))
    html = html.replace("__LIVE_SECTION__", live_section)
    html = html.replace("__NOTICE__", notice_html)
    html = html.replace("__CAVEATS__", caveats_html)
    return html


def write_report_html(data: List[Dict], out_path: str, with_live: bool = True,
                       kb_laws: Optional[int] = None,
                       kb_articles: Optional[int] = None) -> str:
    """Render and write the HTML report to ``out_path``; returns the path."""
    html = build_report_html(data, with_live=with_live,
                             kb_laws=kb_laws, kb_articles=kb_articles)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def render(result: Dict, scenario: Dict, answer: str, fmt: str = "md") -> str:
    if fmt == "md":
        return build_memo_md(scenario, answer, result)
    raise ValueError(f"unsupported format: {fmt}")
