/* 合规三角 · 前端交互（零依赖、无构建步骤）
 * 仅通过 /api/* 与后端通信；所有渲染都先转义，避免把用户粘贴的文本当 HTML。
 */
(function () {
  "use strict";

  var TOKEN_KEY = "ct_token";
  var token = localStorage.getItem(TOKEN_KEY) || "";
  var state = { user: null, usage: null, meta: null, mode: "login" };

  var $ = function (id) { return document.getElementById(id); };

  /* ---------------- helpers ---------------- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function badgeClass(badge) {
    if (badge === "\u{1F7E2}") return "green";
    if (badge === "\u{1F7E1}") return "yellow";
    if (badge === "\u{1F534}") return "red";
    return "gray";
  }

  function fmtTime(ts) {
    if (!ts) return "";
    var d = new Date(ts * 1000);
    var p = function (n) { return n < 10 ? "0" + n : "" + n; };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
           " " + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  function api(method, path, body) {
    var opts = { method: method, headers: {} };
    if (token) { opts.headers["Authorization"] = "Bearer " + token; }
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) {
          var err = new Error(data.error || ("HTTP " + r.status));
          err.status = r.status;
          err.data = data;
          throw err;
        }
        return data;
      });
    });
  }

  function showError(msg) {
    var el = $("authError");
    if (!el) { return; }
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  /* ---------------- auth ---------------- */
  function setMode(next) {
    state.mode = next;
    var reg = next === "register";
    $("authTitle").textContent = reg ? "注册" : "登录";
    $("authSub").textContent = reg
      ? "注册后即可保存核验历史，并享有每月 50 次免费额度"
      : "用邮箱登录以保存核验历史与用量配额";
    $("nameField").classList.toggle("hidden", !reg);
    $("authSubmit").textContent = reg ? "注册并登录" : "登录";
    $("switchText").textContent = reg ? "已经有账号了？" : "还没有账号？";
    $("switchLink").textContent = reg ? "登录" : "注册";
    $("authError").classList.add("hidden");
  }

  function submitAuth() {
    var email = $("email").value.trim();
    var password = $("password").value;
    var payload = { email: email, password: password };
    if (state.mode === "register") {
      payload.display_name = $("displayName").value.trim();
    }
    var path = state.mode === "register" ? "/api/auth/register" : "/api/auth/login";
    $("authSubmit").disabled = true;
    $("authSubmit").textContent = "处理中…";
    api("POST", path, payload).then(function (data) {
      token = data.token;
      localStorage.setItem(TOKEN_KEY, token);
      afterLogin(data);
    }).catch(function (e) {
      showError(e.message);
    }).then(function () {
      $("authSubmit").disabled = false;
      setMode(state.mode);
    });
  }

  function afterLogin(data) {
    state.user = data.user;
    state.usage = data.usage;
    $("view-auth").classList.add("hidden");
    $("view-app").classList.remove("hidden");
    $("userChip").textContent = data.user.email;
    $("userChip").classList.remove("hidden");
    $("logoutBtn").classList.remove("hidden");
    loadMeta();
    loadUsage();
    loadHistory();
    loadKeys();
  }

  function logout() {
    api("POST", "/api/auth/logout", {}).catch(function () {});
    token = "";
    localStorage.removeItem(TOKEN_KEY);
    $("view-app").classList.add("hidden");
    $("view-auth").classList.remove("hidden");
    $("userChip").classList.add("hidden");
    $("logoutBtn").classList.add("hidden");
    $("password").value = "";
  }

  /* ---------------- meta / usage ---------------- */
  function loadMeta() {
    api("GET", "/api/meta").then(function (m) {
      state.meta = m;
      $("kbBadge").textContent = m.kb_available
        ? ("法条库 " + m.kb_laws + " 部 / " + m.kb_articles + " 条")
        : "法条库未加载";
    }).catch(function () {
      $("kbBadge").textContent = "法条库状态未知";
    });
  }

  function loadUsage() {
    api("GET", "/api/me").then(function (data) {
      state.usage = data.usage;
      renderUsage();
    }).catch(function () {});
  }

  function renderUsage() {
    var u = state.usage;
    if (!u) { return; }
    var pct = u.quota > 0 ? Math.min(100, Math.round(u.used / u.quota * 100)) : 0;
    $("usageBox").innerHTML =
      '<div class="usage-num">' + u.used + ' <span class="small muted">/ ' + u.quota + ' 次</span></div>' +
      '<div class="usage-bar"><div class="usage-fill" style="width:' + pct + '%"></div></div>' +
      '<div class="small muted">本月（' + esc(u.period) + '）已使用 ' + u.used +
      ' 次，剩余 ' + u.remaining + ' 次 · 套餐 ' + esc(u.plan) + '</div>';
  }

  /* ---------------- verify ---------------- */
  function renderResult(result) {
    var box = $("resultBox");
    if (!result || !result.items || result.items.length === 0) {
      box.className = "empty";
      box.innerHTML = '<div class="verdict gray">' + esc(result.overall ||
        "未检测到法条引注") + '</div>' +
        '<p class="small muted">回答中未包含「《法律名称》第X条」形式的引注，系统无从核验。</p>';
      return;
    }
    var cls = badgeClass(result.items[0].badge);
    var counts = result.counts || {};
    var html = '<div class="verdict ' + verdictClass(result) + '">' +
      esc(result.overall) + '</div>';
    html += '<div class="counts">' +
      '<span>\u{1F7E2} 通过 ' + (counts["\u{1F7E2}"] || 0) + '</span>' +
      '<span>\u{1F7E1} 待复核 ' + (counts["\u{1F7E1}"] || 0) + '</span>' +
      '<span>\u{1F534} 未通过 ' + (counts["\u{1F534}"] || 0) + '</span>' +
      '</div>';

    result.items.forEach(function (it) {
      html += '<div class="cite ' + badgeClass(it.badge) + '">' +
        '<div class="cite-head">' +
        '<span class="cite-badge">' + it.badge + '</span>' +
        '<span class="cite-law">' + esc(it.raw_law) + '</span>' +
        '<span class="cite-art">第 ' + esc(it.article_no) + ' 条</span>' +
        '<span class="cite-status">' + esc(it.status) + '</span>' +
        '</div>' +
        '<p class="cite-note">' + esc(it.note) + '</p>';
      if (it.quoted) {
        html += '<div class="cite-quote"><b>AI 引述：</b>' + esc(it.quoted) + '</div>';
      }
      if (it.ground_truth) {
        html += '<div class="cite-quote"><b>官方原文：</b>' + esc(it.ground_truth) + '</div>';
      }
      html += '</div>';
    });

    box.className = "";
    box.innerHTML = html;
  }

  function verdictClass(result) {
    var counts = result.counts || {};
    if (counts["\u{1F534}"]) { return "red"; }
    if (counts["\u{1F7E1}"]) { return "yellow"; }
    if (counts["\u{1F7E2}"]) { return "green"; }
    return "gray";
  }

  function verify() {
    var answer = $("answerInput").value;
    if (!answer.trim()) {
      $("resultBox").className = "empty";
      $("resultBox").innerHTML = '<span style="color:var(--red)">请先粘贴需要核验的内容。</span>';
      return;
    }
    var btn = $("verifyBtn");
    btn.disabled = true;
    btn.textContent = "核验中…";
    $("resultBox").className = "empty";
    $("resultBox").textContent = "正在逐条核验…";

    api("POST", "/api/verify", {
      answer: answer,
      as_of_date: $("asOf").value || "2026-08-01"
    }).then(function (data) {
      renderResult(data.result);
      state.usage = data.usage;
      renderUsage();
      loadHistory();
    }).catch(function (e) {
      $("resultBox").innerHTML = '<span style="color:var(--red)">' + esc(e.message) + "</span>";
    }).then(function () {
      btn.disabled = false;
      btn.textContent = "开始核验";
    });
  }

  /* ---------------- history ---------------- */
  function loadHistory() {
    api("GET", "/api/analyses?limit=50").then(function (data) {
      var box = $("historyBox");
      var items = data.items || [];
      if (!items.length) {
        box.className = "empty";
        box.textContent = "暂无历史记录。";
        return;
      }
      var html = "";
      items.forEach(function (it) {
        html += '<div class="hist-item" data-id="' + it.id + '">' +
          '<span class="hist-title">' + esc(it.title || "(无标题)") + "</span>" +
          '<span class="hist-meta">' + esc(it.kind) + " · " + fmtTime(it.created_at) + "</span>" +
          "</div>";
      });
      box.className = "";
      box.innerHTML = html;
      Array.prototype.forEach.call(box.querySelectorAll(".hist-item"), function (el) {
        el.addEventListener("click", function () {
          openAnalysis(el.getAttribute("data-id"));
        });
      });
    }).catch(function (e) {
      $("historyBox").className = "empty";
      $("historyBox").textContent = "加载失败：" + e.message;
    });
  }

  function openAnalysis(id) {
    api("GET", "/api/analyses/" + id).then(function (data) {
      $("answerInput").value = data.input_text || "";
      renderResult(data.result);
      switchTab("workspace");
      window.scrollTo({ top: 0, behavior: "smooth" });
    }).catch(function (e) {
      alert("打开失败：" + e.message);
    });
  }

  /* ---------------- api keys ---------------- */
  function loadKeys() {
    api("GET", "/api/keys").then(function (data) {
      var box = $("keyBox");
      var items = data.items || [];
      if (!items.length) {
        box.className = "empty";
        box.textContent = "暂无密钥。";
        return;
      }
      var html = "";
      items.forEach(function (k) {
        html += '<div class="key-item">' +
          "<code class=\"" + (k.revoked ? "key-revoked" : "") + "\">" + esc(k.key) + "</code>" +
          '<span class="hist-meta">' + esc(k.label) + "</span>" +
          (k.revoked ? '<span class="hist-meta">已吊销</span>'
                     : '<button class="btn-ghost" data-revoke="' + esc(k.key) + '">吊销</button>') +
          "</div>";
      });
      box.className = "";
      box.innerHTML = html;
      Array.prototype.forEach.call(box.querySelectorAll("[data-revoke]"), function (el) {
        el.addEventListener("click", function () {
          api("DELETE", "/api/keys/" + el.getAttribute("data-revoke"))
            .then(loadKeys).catch(function (e) { alert("吊销失败：" + e.message); });
        });
      });
    }).catch(function () {
      $("keyBox").className = "empty";
      $("keyBox").textContent = "加载失败";
    });
  }

  function createKey() {
    var label = $("keyLabel").value.trim() || "default";
    api("POST", "/api/keys", { label: label }).then(function (data) {
      var box = $("keyBox");
      var note = document.createElement("div");
      note.className = "new-key";
      note.innerHTML = "<strong>新密钥（只显示一次）：</strong><br>" + esc(data.key);
      box.parentNode.insertBefore(note, box.nextSibling);
      $("keyLabel").value = "";
      loadKeys();
    }).catch(function (e) { alert("创建失败：" + e.message); });
  }

  /* ---------------- tabs ---------------- */
  function switchTab(name) {
    Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
      t.classList.toggle("active", t.getAttribute("data-tab") === name);
    });
    ["workspace", "history", "account"].forEach(function (n) {
      $("tab-" + n).classList.toggle("hidden", n !== name);
    });
  }

  /* ---------------- wiring ---------------- */
  document.addEventListener("DOMContentLoaded", function () {
    $("switchLink").addEventListener("click", function (e) {
      e.preventDefault();
      setMode(state.mode === "login" ? "register" : "login");
    });
    $("authSubmit").addEventListener("click", submitAuth);
    $("password").addEventListener("keydown", function (e) {
      if (e.key === "Enter") { submitAuth(); }
    });
    $("logoutBtn").addEventListener("click", logout);
    $("verifyBtn").addEventListener("click", verify);
    $("createKeyBtn").addEventListener("click", createKey);
    Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
      t.addEventListener("click", function () { switchTab(t.getAttribute("data-tab")); });
    });

    setMode("login");

    // Restore an existing session if the token is still valid.
    if (token) {
      api("GET", "/api/me").then(afterLogin).catch(function () {
        token = "";
        localStorage.removeItem(TOKEN_KEY);
      });
    }
  });
})();
