/* LocalGPT frontend - vanilla JS, no external dependencies */
(function () {
  "use strict";

  /* ------------------------------------------------------------------ */
  /* Icons                                                              */
  /* ------------------------------------------------------------------ */
  const svg = (body, viewBox) =>
    `<svg viewBox="${viewBox || "0 0 24 24"}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;

  const ICONS = {
    logo: svg('<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/><path d="M8.5 10h7M8.5 13.5h4.5"/>'),
    chat: svg('<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>'),
    trash: svg('<path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/>'),
    copy: svg('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'),
    check: svg('<path d="M20 6 9 17l-5-5"/>'),
    error: svg('<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/>'),
    warning: svg('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17v.01"/>'),
    success: svg('<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>'),
    info: svg('<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5v.01"/>'),
  };

  /* ------------------------------------------------------------------ */
  /* State + DOM                                                        */
  /* ------------------------------------------------------------------ */
  const state = {
    conversations: [],
    activeId: null,
    active: null,
    status: null,
    streaming: false,
    abortController: null,
    creatingPromise: null,
    model: "llama3.2:3b",
    realtime: null,
    webSearchEnabled: false,
    webSearchAvailable: false,
  };

  const el = {};
  const $ = (id) => document.getElementById(id);

  function cacheDom() {
    el.app = $("app");
    el.sidebar = $("sidebar");
    el.overlay = $("sidebar-overlay");
    el.menuToggle = $("menu-toggle");
    el.sidebarClose = $("sidebar-close");
    el.newChat = $("new-chat");
    el.conversationList = $("conversation-list");
    el.conversationCount = $("conversation-count");
    el.statusCard = $("status-card");
    el.statusDot = $("status-dot");
    el.statusText = $("status-text");
    el.statusDetail = $("status-detail");
    el.modelName = $("model-name");
    el.modelDot = $("model-dot");
    el.realtimePill = $("realtime-pill");
    el.realtimeText = $("realtime-text");
    el.realtimeDot = $("realtime-dot");
    el.webPill = $("web-pill");
    el.webStatus = $("web-status");
    el.chatTitle = $("chat-title");
    el.chatSubtitle = $("chat-subtitle");
    el.clearChat = $("clear-chat");
    el.chatScroll = $("chat-scroll");
    el.welcome = $("welcome");
    el.messages = $("messages");
    el.composer = $("composer");
    el.input = $("input");
    el.send = $("send");
    el.stop = $("stop");
    el.toastStack = $("toast-stack");
    el.modal = $("modal");
    el.modalTitle = $("modal-title");
    el.modalText = $("modal-text");
    el.modalConfirm = $("modal-confirm");
    el.modalCancel = $("modal-cancel");
  }

  /* ------------------------------------------------------------------ */
  /* Utilities                                                          */
  /* ------------------------------------------------------------------ */
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatTime(iso) {
    const date = iso ? new Date(iso) : new Date();
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function formatRelative(iso) {
    const date = iso ? new Date(iso) : null;
    if (!date || Number.isNaN(date.getTime())) return "";
    const now = new Date();
    const diff = now - date;
    const day = 86400000;
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    if (date.getTime() >= startOfToday) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    if (date.getTime() >= startOfToday - day) return "Yesterday";
    if (diff < 7 * day) return date.toLocaleDateString([], { weekday: "short" });
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  }

  function formatStats(stats) {
    if (!stats) return "";
    const parts = [];
    if (stats.eval_count) parts.push(`${stats.eval_count} tokens`);
    if (stats.total_duration) {
      const seconds = stats.total_duration / 1e9;
      parts.push(seconds >= 10 ? `${Math.round(seconds)}s` : `${seconds.toFixed(1)}s`);
    }
    return parts.join(" \u00b7 ");
  }

  function isNearBottom(threshold) {
    const node = el.chatScroll;
    return node.scrollHeight - node.scrollTop - node.clientHeight < (threshold || 140);
  }

  function scrollToBottom(force) {
    if (!force && !isNearBottom()) return;
    el.chatScroll.scrollTop = el.chatScroll.scrollHeight;
  }

  /* ------------------------------------------------------------------ */
  /* Markdown                                                           */
  /* ------------------------------------------------------------------ */
  function inline(text) {
    let out = escapeHtml(text);
    const codes = [];
    out = out.replace(/`([^`\n]+)`/g, function (_, code) {
      codes.push(code);
      return "\u0000C" + (codes.length - 1) + "\u0000";
    });

    const links = [];
    out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, function (_, label, url) {
      links.push(
        '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + label + "</a>"
      );
      return "\u0000L" + (links.length - 1) + "\u0000";
    });
    out = out.replace(/\bhttps?:\/\/[^\s<)\u0000]+/g, function (raw) {
      const match = /^(.*?)([.,;:!?]*)$/.exec(raw);
      const url = match ? match[1] : raw;
      const tail = match ? match[2] : "";
      return (
        '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + "</a>" + tail
      );
    });

    out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/__([^_\n]+)__/g, "<strong>$1</strong>");
    out = out.replace(/(^|[^*\w])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    out = out.replace(/(^|[^_\w])_([^_\n]+)_/g, "$1<em>$2</em>");
    out = out.replace(/~~([^~\n]+)~~/g, "<del>$1</del>");

    out = out.replace(/\u0000C(\d+)\u0000/g, function (_, idx) {
      return '<code class="inline-code">' + codes[Number(idx)] + "</code>";
    });
    out = out.replace(/\u0000L(\d+)\u0000/g, function (_, idx) {
      return links[Number(idx)];
    });
    return out;
  }

  const LANG_ALIASES = {
    js: "javascript",
    jsx: "javascript",
    ts: "typescript",
    tsx: "typescript",
    py: "python",
    sh: "bash",
    shell: "bash",
    zsh: "bash",
    powershell: "powershell",
    ps1: "powershell",
    yml: "yaml",
    md: "markdown",
    c: "c",
    h: "c",
    cpp: "cpp",
    "c++": "cpp",
    cs: "csharp",
    "c#": "csharp",
    html: "html",
    htm: "html",
    xml: "html",
    svg: "html",
    json: "json",
    css: "css",
    scss: "css",
    sql: "sql",
    rs: "rust",
    go: "go",
    java: "java",
    kt: "kotlin",
    rb: "ruby",
    php: "php",
  };

  const KEYWORDS = {
    python: "False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case self".split(" "),
    javascript: "async await break case catch class const continue debugger default delete do else export extends finally for from function get if import in instanceof let new of return set static super switch this throw try typeof var void while with yield true false null undefined".split(" "),
    typescript: "abstract any as async await boolean break case catch class const continue declare default delete do else enum export extends false finally for from function get if implements import in instanceof interface keyof let namespace never new null number of private protected public readonly return set static string super switch symbol this throw true try type typeof undefined unique unknown var void while yield".split(" "),
    java: "abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null".split(" "),
    c: "auto break case char const continue default do double else enum extern float for goto if inline int long register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while true false NULL".split(" "),
    cpp: "alignas alignof and asm auto bool break case catch char class const constexpr continue decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept nullptr operator private protected public register reinterpret_cast return short signed sizeof static static_cast struct switch template this throw true try typedef typeid typename union unsigned using virtual void volatile while".split(" "),
    csharp: "abstract as base bool break byte case catch char checked class const continue decimal default delegate do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int interface internal is lock long namespace new null object operator out override params private protected public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual void volatile while async await var".split(" "),
    rust: "as async await break const continue crate dyn else enum extern false fn for if impl in let loop match mod move mut pub ref return self Self static struct super trait true type unsafe use where while".split(" "),
    go: "break case chan const continue default defer else fallthrough for func go goto if import interface map package range return select struct switch type var true false nil".split(" "),
    kotlin: "as break class continue do else false for fun if in interface is null object package return super this throw true try typealias typeof val var when while".split(" "),
    ruby: "alias and begin break case class def defined do else elsif end ensure false for if in module next nil not or redo rescue retry return self super then true undef unless until when while yield".split(" "),
    php: "abstract and array as break callable case catch class clone const continue declare default do echo else elseif empty enddeclare endfor endforeach endif endswitch endwhile eval exit extends final finally fn for foreach function global goto if implements include include_once instanceof insteadof interface isset list match namespace new null or print private protected public readonly require require_once return static switch throw trait true try unset use var while xor yield".split(" "),
    sql: "select from where and or not insert into values update set delete create table drop alter add column primary key foreign references join left right inner outer full on as group by order having limit offset distinct union all case when then else end null is in like between exists count sum avg min max".split(" "),
    bash: "if then else elif fi for while until do done case esac function in select time coproc return exit break continue local export readonly declare unset shift source alias echo cd pwd ls mkdir rm cp mv cat grep sed awk curl wget git python pip npm node ollama".split(" "),
    powershell: "if else elseif switch foreach for while do until function filter param return break continue try catch finally throw trap begin process end in class enum using hidden static".split(" "),
    yaml: "true false null yes no on off".split(" "),
    markdown: [],
  };

  const CSS_KEYWORDS = "important media supports keyframes font-face import from to and or not only screen print all hover focus active visited disabled checked before after first-child last-child nth-child root var calc rgb rgba hsl hsla linear-gradient radial-gradient flex grid block inline none absolute relative fixed sticky auto inherit initial unset".split(" ");

  function normalizeLang(lang) {
    const value = String(lang || "").toLowerCase().trim();
    return LANG_ALIASES[value] || value;
  }

  function highlightGeneric(code, keywords, options) {
    const opts = options || {};
    const commentParts = ["\\/\\*[\\s\\S]*?\\*\\/", "\\/\\/[^\\n]*"];
    if (opts.hash) commentParts.push("#[^\\n]*");
    if (opts.dash) commentParts.push("--[^\\n]*");
    const kw = (keywords || [])
      .filter(Boolean)
      .map(function (word) {
        return word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      })
      .join("|");

    let pattern =
      "(" + commentParts.join("|") + ")" +
      "|(\"\"\"[\\s\\S]*?\"\"\"|'''[\\s\\S]*?'''|\"(?:\\\\.|[^\"\\\\\\n])*\"|'(?:\\\\.|[^'\\\\\\n])*'|`(?:\\\\.|[^`\\\\])*`)" +
      "|(\\b(?:0[xX][0-9a-fA-F]+|\\d+(?:\\.\\d+)?)\\b)" +
      (kw ? "|(\\b(?:" + kw + ")\\b)" : "|(x^)") +
      "|([A-Za-z_$][\\w$]*)(?=\\s*\\()";

    const re = new RegExp(pattern, "g");
    let out = "";
    let last = 0;
    let match;
    while ((match = re.exec(code))) {
      out += escapeHtml(code.slice(last, match.index));
      if (match[1]) out += '<span class="tok-comment">' + escapeHtml(match[1]) + "</span>";
      else if (match[2]) out += '<span class="tok-string">' + escapeHtml(match[2]) + "</span>";
      else if (match[3]) out += '<span class="tok-number">' + escapeHtml(match[3]) + "</span>";
      else if (match[4]) out += '<span class="tok-keyword">' + escapeHtml(match[4]) + "</span>";
      else if (match[5]) out += '<span class="tok-function">' + escapeHtml(match[5]) + "</span>";
      last = re.lastIndex;
      if (re.lastIndex === match.index) re.lastIndex++;
    }
    out += escapeHtml(code.slice(last));
    return out;
  }

  function highlightAttrs(raw) {
    const re = /([\w:-]+)(=)("[^"]*"|'[^']*'|[^\s>]+)?/g;
    let out = "";
    let last = 0;
    let match;
    while ((match = re.exec(raw))) {
      out += escapeHtml(raw.slice(last, match.index));
      out += '<span class="tok-attr">' + escapeHtml(match[1]) + "</span>";
      if (match[2]) out += escapeHtml(match[2]);
      if (match[3]) out += '<span class="tok-string">' + escapeHtml(match[3]) + "</span>";
      last = re.lastIndex;
    }
    out += escapeHtml(raw.slice(last));
    return out;
  }

  function highlightHtml(code) {
    const re = /(<!--[\s\S]*?-->)|(<\/?)([a-zA-Z][\w:-]*)((?:\s+[\w:-]+(?:=(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)(\/?>)/g;
    let out = "";
    let last = 0;
    let match;
    while ((match = re.exec(code))) {
      out += escapeHtml(code.slice(last, match.index));
      if (match[1]) {
        out += '<span class="tok-comment">' + escapeHtml(match[1]) + "</span>";
      } else {
        out += '<span class="tok-tag">' + escapeHtml(match[2] + match[3]) + "</span>";
        out += highlightAttrs(match[4] || "");
        out += '<span class="tok-tag">' + escapeHtml(match[5]) + "</span>";
      }
      last = re.lastIndex;
    }
    out += escapeHtml(code.slice(last));
    return out;
  }

  function highlightJson(code) {
    const re = /("(?:\\.|[^"\\])*")(\s*:)?|(\b(?:true|false|null)\b)|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)/g;
    let out = "";
    let last = 0;
    let match;
    while ((match = re.exec(code))) {
      out += escapeHtml(code.slice(last, match.index));
      if (match[1]) {
        const cls = match[2] ? "tok-attr" : "tok-string";
        out += '<span class="' + cls + '">' + escapeHtml(match[1]) + "</span>";
        if (match[2]) out += escapeHtml(match[2]);
      } else if (match[3]) {
        out += '<span class="tok-literal">' + escapeHtml(match[3]) + "</span>";
      } else if (match[4]) {
        out += '<span class="tok-number">' + escapeHtml(match[4]) + "</span>";
      }
      last = re.lastIndex;
    }
    out += escapeHtml(code.slice(last));
    return out;
  }

  function highlight(code, lang) {
    const language = normalizeLang(lang);
    if (language === "html") return highlightHtml(code);
    if (language === "json") return highlightJson(code);
    if (language === "css" || language === "scss") {
      return highlightGeneric(code, CSS_KEYWORDS, {});
    }
    if (language === "sql") {
      return highlightGeneric(code, KEYWORDS.sql, { dash: true });
    }
    if (language === "bash") {
      return highlightGeneric(code, KEYWORDS.bash, { hash: true });
    }
    if (language === "powershell") {
      return highlightGeneric(code, KEYWORDS.powershell, { hash: true });
    }
    if (language === "python" || language === "ruby") {
      return highlightGeneric(code, KEYWORDS[language], { hash: true });
    }
    return highlightGeneric(code, KEYWORDS[language] || [], {});
  }

  function codeBlockHtml(code, lang) {
    const language = normalizeLang(lang) || "text";
    const label = language === "text" ? "code" : language;
    const encoded = encodeURIComponent(code);
    return (
      '<div class="code-block"><div class="code-head">' +
      '<span class="code-lang">' + escapeHtml(label) + "</span>" +
      '<button class="code-copy" type="button" data-code="' + encoded + '" aria-label="Copy code">' +
      ICONS.copy + "<span>Copy</span></button></div>" +
      "<pre><code>" + highlight(code, language) + "</code></pre></div>"
    );
  }

  function isTableSeparator(line) {
    return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);
  }

  function renderMarkdown(source) {
    if (!source) return "";
    const lines = String(source).replace(/\r\n?/g, "\n").split("\n");
    let html = "";
    let i = 0;

    const isBlank = (line) => !line.trim();
    const isFence = (line) => /^\s{0,3}```/.test(line);
    const isHeading = (line) => /^\s{0,3}#{1,6}\s+/.test(line);
    const isHr = (line) => /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line);
    const isQuote = (line) => /^\s{0,3}>\s?/.test(line);
    const isList = (line) => /^\s{0,3}([-*+]|\d+[.)])\s+/.test(line);
    const startsBlock = (line) => isFence(line) || isHeading(line) || isHr(line) || isQuote(line) || isList(line);

    while (i < lines.length) {
      const line = lines[i];

      if (isBlank(line)) {
        i++;
        continue;
      }

      if (isFence(line)) {
        const fenceMatch = /^\s{0,3}```\s*([^\s`]*)/.exec(line);
        const lang = fenceMatch && fenceMatch[1] ? fenceMatch[1] : "";
        i++;
        const buffer = [];
        while (i < lines.length && !/^\s{0,3}```\s*$/.test(lines[i])) {
          buffer.push(lines[i]);
          i++;
        }
        if (i < lines.length) i++;
        html += codeBlockHtml(buffer.join("\n"), lang);
        continue;
      }

      if (isHeading(line)) {
        const heading = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
        if (heading) {
          const level = heading[1].length;
          html += "<h" + level + ">" + inline(heading[2]) + "</h" + level + ">";
          i++;
          continue;
        }
      }

      if (isHr(line)) {
        html += "<hr>";
        i++;
        continue;
      }

      if (isQuote(line)) {
        const buffer = [];
        while (i < lines.length && isQuote(lines[i])) {
          buffer.push(lines[i].replace(/^\s{0,3}>\s?/, ""));
          i++;
        }
        html += "<blockquote>" + renderMarkdown(buffer.join("\n")) + "</blockquote>";
        continue;
      }

      if (line.indexOf("|") !== -1 && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
        const splitRow = (row) => {
          let value = row.trim();
          if (value.startsWith("|")) value = value.slice(1);
          if (value.endsWith("|")) value = value.slice(0, -1);
          return value.split("|").map((cell) => cell.trim());
        };
        const header = splitRow(line);
        const align = splitRow(lines[i + 1]).map(function (cell) {
          const left = cell.startsWith(":");
          const right = cell.endsWith(":");
          if (left && right) return "center";
          if (right) return "right";
          if (left) return "left";
          return "";
        });
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].indexOf("|") !== -1 && !isBlank(lines[i])) {
          rows.push(splitRow(lines[i]));
          i++;
        }
        html += "<table><thead><tr>";
        header.forEach(function (cell, index) {
          const style = align[index] ? ' style="text-align:' + align[index] + '"' : "";
          html += "<th" + style + ">" + inline(cell) + "</th>";
        });
        html += "</tr></thead><tbody>";
        rows.forEach(function (row) {
          html += "<tr>";
          header.forEach(function (_, index) {
            const style = align[index] ? ' style="text-align:' + align[index] + '"' : "";
            html += "<td" + style + ">" + inline(row[index] || "") + "</td>";
          });
          html += "</tr>";
        });
        html += "</tbody></table>";
        continue;
      }

      if (isList(line)) {
        const ordered = /^\s{0,3}\d+[.)]\s+/.test(line);
        const first = /^\s{0,3}(\d+)[.)]\s+/.exec(line);
        const start = ordered && first ? parseInt(first[1], 10) : 1;
        const items = [];
        while (i < lines.length && !isBlank(lines[i])) {
          const item = /^\s{0,3}([-*+]|\d+[.)])\s+(.*)$/.exec(lines[i]);
          if (item) {
            items.push(item[2]);
            i++;
          } else if (items.length && /^\s{2,}\S/.test(lines[i])) {
            items[items.length - 1] += "\n" + lines[i].trim();
            i++;
          } else {
            break;
          }
        }
        const tag = ordered ? "ol" : "ul";
        const startAttr = ordered && start !== 1 ? ' start="' + start + '"' : "";
        html += "<" + tag + startAttr + ">";
        items.forEach(function (item) {
          const task = /^\[([ xX])\]\s+/.exec(item);
          if (task) {
            const checked = task[1].toLowerCase() === "x";
            html +=
              '<li class="task-item"><span class="task-box' + (checked ? " checked" : "") + '">' +
              (checked ? "&#10003;" : "") + "</span>" +
              inline(item.slice(task[0].length)).replace(/\n/g, "<br>") + "</li>";
          } else {
            html += "<li>" + inline(item).replace(/\n/g, "<br>") + "</li>";
          }
        });
        html += "</" + tag + ">";
        continue;
      }

      const paragraph = [line];
      i++;
      while (
        i < lines.length &&
        !isBlank(lines[i]) &&
        !startsBlock(lines[i]) &&
        !(lines[i].indexOf("|") !== -1 && i + 1 < lines.length && isTableSeparator(lines[i + 1]))
      ) {
        paragraph.push(lines[i]);
        i++;
      }
      html += "<p>" + inline(paragraph.join("\n")).replace(/\n/g, "<br>") + "</p>";
    }

    return html;
  }

  /* ------------------------------------------------------------------ */
  /* API                                                                */
  /* ------------------------------------------------------------------ */
  class ApiError extends Error {
    constructor(message, status, code) {
      super(message);
      this.name = "ApiError";
      this.status = status || 0;
      this.code = code || "error";
    }
  }

  async function api(path, options) {
    const opts = Object.assign({ headers: {} }, options || {});
    if (opts.body && !opts.headers["Content-Type"]) {
      opts.headers["Content-Type"] = "application/json";
    }
    let response;
    try {
      response = await fetch(path, opts);
    } catch (err) {
      throw new ApiError(
        "Cannot reach the LocalGPT server. Make sure app.py is running.",
        0,
        "network_error"
      );
    }
    const contentType = response.headers.get("content-type") || "";
    let data = null;
    if (contentType.indexOf("application/json") !== -1) {
      data = await response.json().catch(function () { return null; });
    }
    if (!response.ok) {
      const message =
        (data && (data.message || data.error)) || "Request failed (" + response.status + ")";
      throw new ApiError(message, response.status, data && data.error);
    }
    return data;
  }

  function parseSseEvent(raw) {
    let event = "message";
    const dataLines = [];
    raw.split("\n").forEach(function (line) {
      if (!line || line.startsWith(":")) return;
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
    });
    if (!dataLines.length) return null;
    try {
      return { event: event, data: JSON.parse(dataLines.join("\n")) };
    } catch (err) {
      return null;
    }
  }

  async function streamChat(conversationId, message, signal, onEvent) {
    let response;
    try {
      response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ conversation_id: conversationId, message: message }),
        signal: signal,
      });
    } catch (err) {
      if (err && err.name === "AbortError") throw err;
      throw new ApiError(
        "Cannot reach the LocalGPT server. Make sure app.py is running.",
        0,
        "network_error"
      );
    }

    if (!response.ok) {
      let data = null;
      try {
        data = await response.json();
      } catch (err) {
        data = null;
      }
      throw new ApiError(
        (data && (data.message || data.error)) || "Request failed (" + response.status + ")",
        response.status,
        data && data.error
      );
    }
    if (!response.body) {
      throw new ApiError("Streaming is not supported by this browser.", 0, "no_stream");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let terminal = false;

    const handleRaw = function (raw) {
      const evt = parseSseEvent(raw);
      if (!evt) return;
      if (evt.event === "done" || evt.event === "error") terminal = true;
      onEvent(evt.event, evt.data);
    };

    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      let match;
      while ((match = buffer.match(/\r?\n\r?\n/))) {
        const index = match.index;
        const raw = buffer.slice(0, index);
        buffer = buffer.slice(index + match[0].length);
        if (raw.trim()) handleRaw(raw);
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) handleRaw(buffer);
    if (!terminal) {
      throw new ApiError(
        "The connection ended before the reply was complete.",
        0,
        "stream_incomplete"
      );
    }
  }

  /* ------------------------------------------------------------------ */
  /* Toasts + modal                                                     */
  /* ------------------------------------------------------------------ */
  function toast(message, type, timeout) {
    const kind = type || "info";
    const node = document.createElement("div");
    node.className = "toast " + kind;
    node.innerHTML = ICONS[kind] || ICONS.info;
    const text = document.createElement("div");
    text.className = "toast-msg";
    text.textContent = message;
    node.appendChild(text);
    el.toastStack.appendChild(node);
    const life = timeout || (kind === "error" ? 7000 : 4200);
    setTimeout(function () {
      node.classList.add("leaving");
      setTimeout(function () { node.remove(); }, 220);
    }, life);
  }

  let modalResolver = null;

  function confirmDialog(options) {
    const opts = options || {};
    el.modalTitle.textContent = opts.title || "Are you sure?";
    el.modalText.textContent = opts.text || "This action cannot be undone.";
    el.modalConfirm.textContent = opts.confirmLabel || "Delete";
    el.modalConfirm.className = "btn " + (opts.danger === false ? "ghost" : "danger");
    el.modal.hidden = false;
    setTimeout(function () { el.modalConfirm.focus(); }, 30);
    return new Promise(function (resolve) {
      modalResolver = resolve;
    });
  }

  function closeModal(result) {
    if (el.modal.hidden) return;
    el.modal.hidden = true;
    const resolve = modalResolver;
    modalResolver = null;
    if (resolve) resolve(result);
  }

  /* ------------------------------------------------------------------ */
  /* Sidebar + status                                                   */
  /* ------------------------------------------------------------------ */
  function openSidebar() {
    el.sidebar.classList.add("open");
    el.overlay.hidden = false;
    el.menuToggle.setAttribute("aria-expanded", "true");
  }

  function closeSidebar() {
    el.sidebar.classList.remove("open");
    el.overlay.hidden = true;
    el.menuToggle.setAttribute("aria-expanded", "false");
  }

  function setStatus(stateName, text, detail) {
    el.statusDot.dataset.state = stateName;
    el.modelDot.dataset.state = stateName;
    el.statusText.textContent = text;
    el.statusDetail.textContent = detail || "";
  }

  function applyStatus(status) {
    state.status = status;
    if (status && status.app && status.app.model) state.model = status.app.model;
    if (status && status.model) state.model = status.model;
    el.modelName.textContent = state.model;
    if (!status || !status.online) {
      setStatus("offline", "Ollama offline", "Start Ollama, then refresh");
      el.statusCard.title = (status && status.error) || "Ollama is not reachable";
      updateHeader(state.active);
      return;
    }
    if (!status.model_installed) {
      setStatus("warning", "Model not installed", "Run: ollama pull " + state.model);
      el.statusCard.title = "The configured model is missing.";
    } else {
      const loaded = status.running && status.running.length;
      setStatus(
        "online",
        "Connected to Ollama",
        (status.version ? "v" + status.version + " \u00b7 " : "") + (loaded ? "model loaded" : "model ready")
      );
      const gpu = status.gpu;
      el.statusCard.title = gpu
        ? gpu.name + " \u00b7 " + gpu.memory_total_mb + " MB VRAM" +
          (gpu.memory_used_mb != null ? " \u00b7 " + gpu.memory_used_mb + " MB in use" : "")
        : "Local Ollama runtime";
    }
    updateHeader(state.active);
  }

  async function refreshStatus(force, silent) {
    try {
      const status = await api("/api/status" + (force ? "?force=1" : ""));
      applyStatus(status);
      // Also load config for realtime/web search
      try {
        const cfg = await api("/api/config");
        if (cfg && cfg.realtime) {
          state.realtime = cfg.realtime;
          if (el.realtimeText) {
            el.realtimeText.textContent = (cfg.realtime.time || "--:--") + " \u00b7 " + (cfg.realtime.day || "");
          }
        }
        if (typeof cfg.web_search_enabled !== "undefined") {
          state.webSearchEnabled = cfg.web_search_enabled;
          state.webSearchAvailable = cfg.web_search_available;
          if (el.webPill && el.webStatus) {
            if (cfg.web_search_enabled && cfg.web_search_available) {
              el.webPill.dataset.state = "enabled";
              el.webStatus.textContent = "On";
            } else if (cfg.web_search_enabled) {
              el.webPill.dataset.state = "enabled";
              el.webStatus.textContent = "Limited";
            } else {
              el.webPill.dataset.state = "disabled";
              el.webStatus.textContent = "Off";
            }
          }
        }
      } catch (e) { /* ignore */ }
      if (force && !silent) {
        if (status.online && status.model_installed) toast("Ollama is connected.", "success", 2600);
        else if (status.online) toast("Ollama is running, but " + state.model + " is not installed.", "warning");
        else toast(status.error || "Ollama is not reachable.", "error");
      }
    } catch (err) {
      setStatus("offline", "Server unreachable", "Is app.py running?");
      if (force && !silent) toast(err.message, "error");
    }
  }

  async function updateRealtime() {
    try {
      const data = await api("/api/time");
      if (data && data.ok) {
        state.realtime = data;
        if (el.realtimeText) {
          el.realtimeText.textContent = (data.time || "--:--") + " \u00b7 " + (data.day || "");
        }
      }
    } catch (e) { /* ignore */ }
  }

  /* ------------------------------------------------------------------ */
  /* Conversation list                                                  */
  /* ------------------------------------------------------------------ */
  function renderConversationList() {
    el.conversationList.innerHTML = "";
    el.conversationCount.textContent = String(state.conversations.length);
    if (!state.conversations.length) {
      const empty = document.createElement("div");
      empty.className = "conversation-empty";
      empty.innerHTML = "No conversations yet.<br>Start a new chat to begin.";
      el.conversationList.appendChild(empty);
      return;
    }
    state.conversations.forEach(function (conversation) {
      const item = document.createElement("div");
      item.className = "conversation-item" + (conversation.id === state.activeId ? " active" : "");
      item.dataset.id = String(conversation.id);
      item.setAttribute("role", "button");
      item.tabIndex = 0;
      item.setAttribute("aria-label", "Open conversation: " + (conversation.title || "New chat"));
      item.innerHTML =
        '<span class="chat-icon">' + ICONS.chat + "</span>" +
        '<span class="conversation-main">' +
        '<span class="conversation-title"></span>' +
        '<span class="conversation-meta"></span>' +
        "</span>" +
        '<button class="conversation-delete" type="button" aria-label="Delete conversation" title="Delete conversation">' +
        ICONS.trash + "</button>";

      item.querySelector(".conversation-title").textContent = conversation.title || "New chat";
      const count = conversation.message_count || 0;
      item.querySelector(".conversation-meta").textContent = count
        ? count + " message" + (count === 1 ? "" : "s") + " \u00b7 " + formatRelative(conversation.updated_at)
        : "Empty \u00b7 " + formatRelative(conversation.created_at);

      item.addEventListener("click", function (event) {
        if (event.target.closest(".conversation-delete")) return;
        openConversation(conversation.id);
      });
      item.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openConversation(conversation.id);
        }
      });
      item.querySelector(".conversation-delete").addEventListener("click", function (event) {
        event.stopPropagation();
        deleteConversation(conversation);
      });
      el.conversationList.appendChild(item);
    });
  }

  async function loadConversations() {
    const data = await api("/api/conversations");
    state.conversations = (data && data.conversations) || [];
    renderConversationList();
  }

  /* ------------------------------------------------------------------ */
  /* Header + chat state                                                */
  /* ------------------------------------------------------------------ */
  function activeMessageCount() {
    return el.messages.querySelectorAll(".message").length;
  }

  function updateHeader(conversation) {
    if (!conversation) {
      el.chatTitle.textContent = "New chat";
      el.chatSubtitle.textContent = "Local model \u00b7 " + state.model;
      el.clearChat.disabled = true;
      return;
    }
    const count = activeMessageCount();
    el.chatTitle.textContent = conversation.title || "New chat";
    el.chatSubtitle.textContent = count
      ? count + " message" + (count === 1 ? "" : "s") + " \u00b7 " + state.model
      : "New conversation \u00b7 " + state.model;
    el.clearChat.disabled = count === 0 || state.streaming;
  }

  function showWelcome() {
    el.welcome.hidden = false;
    el.messages.innerHTML = "";
  }

  function resetChat() {
    state.activeId = null;
    state.active = null;
    try {
      localStorage.removeItem("localgpt.active");
    } catch (err) { /* ignore */ }
    showWelcome();
    updateHeader(null);
    renderConversationList();
  }

  function buildMessage(message, options) {
    const opts = options || {};
    const role = message.role === "user" ? "user" : "assistant";
    const article = document.createElement("article");
    article.className = "message " + role + (opts.streaming ? " streaming" : "");
    if (message.id != null) article.dataset.id = String(message.id);

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    if (role === "assistant") avatar.innerHTML = ICONS.logo;
    else avatar.textContent = "You";

    const body = document.createElement("div");
    body.className = "message-body";

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const author = document.createElement("span");
    author.className = "author";
    author.textContent = role === "user" ? "You" : "LocalGPT";
    const sep = document.createElement("span");
    sep.className = "dot-sep";
    const time = document.createElement("span");
    time.className = "time";
    time.textContent = formatTime(message.created_at);
    meta.appendChild(author);
    meta.appendChild(sep);
    meta.appendChild(time);

    const content = document.createElement("div");
    content.className = "message-content";
    let md = null;
    let typing = null;
    if (role === "user") {
      content.textContent = message.content || "";
    } else {
      md = document.createElement("div");
      md.className = "markdown";
      if (message.content) md.innerHTML = renderMarkdown(message.content);
      content.appendChild(md);
      if (opts.streaming) {
        typing = document.createElement("div");
        typing.className = "typing";
        typing.innerHTML = "<span></span><span></span><span></span>";
        content.appendChild(typing);
      }
    }

    const actions = document.createElement("div");
    actions.className = "message-actions";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "msg-action";
    copy.innerHTML = ICONS.copy + "<span>Copy</span>";
    copy.addEventListener("click", function () {
      copyText(message.content || "", copy, "Copy");
    });
    actions.appendChild(copy);

    body.appendChild(meta);
    body.appendChild(content);
    body.appendChild(actions);
    article.appendChild(avatar);
    article.appendChild(body);

    return { article: article, body: body, meta: meta, content: content, md: md, typing: typing, actions: actions, copy: copy };
  }

  function appendCursor(md, cursor) {
    let target = md.lastElementChild;
    while (target && target.lastElementChild && /^(UL|OL|TABLE|TBODY|TR|BLOCKQUOTE|DIV|PRE)$/.test(target.tagName)) {
      target = target.lastElementChild;
    }
    (target || md).appendChild(cursor);
  }

  function appendStats(meta, stats) {
    const text = formatStats(stats);
    if (!text) return;
    const sep = document.createElement("span");
    sep.className = "dot-sep";
    const span = document.createElement("span");
    span.className = "stats";
    span.textContent = text;
    meta.appendChild(sep);
    meta.appendChild(span);
  }

  function setCopyContent(assistant, text) {
    if (!assistant.copy) return;
    const clone = assistant.copy.cloneNode(true);
    assistant.copy.replaceWith(clone);
    assistant.copy = clone;
    clone.addEventListener("click", function () {
      copyText(text, clone, "Copy");
    });
  }

  function addErrorNotice(container, message) {
    const notice = document.createElement("div");
    notice.className = "error-notice";
    notice.innerHTML = ICONS.error;
    const text = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = "Something went wrong";
    const detail = document.createElement("span");
    detail.textContent = message;
    text.appendChild(strong);
    text.appendChild(detail);
    notice.appendChild(text);
    container.appendChild(notice);
  }

  /* ------------------------------------------------------------------ */
  /* Clipboard                                                          */
  /* ------------------------------------------------------------------ */
  async function copyText(text, button, defaultLabel) {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch (err) {
      ok = fallbackCopy(text);
    }
    if (!ok) {
      toast("Could not copy to the clipboard.", "error");
      return;
    }
    if (button) {
      const original = button.innerHTML;
      button.classList.add("copied");
      button.innerHTML = ICONS.check + "<span>Copied</span>";
      setTimeout(function () {
        button.classList.remove("copied");
        button.innerHTML = original;
      }, 1600);
    }
    if (defaultLabel) toast("Copied to clipboard.", "success", 1800);
  }

  function fallbackCopy(text) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.top = "-1000px";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (err) {
      ok = false;
    }
    area.remove();
    return ok;
  }

  /* ------------------------------------------------------------------ */
  /* Conversations actions                                              */
  /* ------------------------------------------------------------------ */
  async function createConversation(options) {
    if (state.creatingPromise) return state.creatingPromise;
    const opts = options || {};
    const run = (async function () {
      const conversation = await api("/api/conversations", {
        method: "POST",
        body: JSON.stringify({}),
      });
      state.conversations.unshift(conversation);
      state.activeId = conversation.id;
      state.active = conversation;
      try {
        localStorage.setItem("localgpt.active", String(conversation.id));
      } catch (err) { /* ignore */ }
      renderConversationList();
      showWelcome();
      updateHeader(conversation);
      if (opts.focus !== false) el.input.focus();
      if (opts.closeSidebar) closeSidebar();
      return conversation;
    })();
    state.creatingPromise = run;
    try {
      return await run;
    } finally {
      state.creatingPromise = null;
      updateSendState();
    }
  }

  async function openConversation(id, options) {
    const opts = options || {};
    if (state.streaming) return;
    try {
      const conversation = await api("/api/conversations/" + id);
      state.activeId = conversation.id;
      state.active = conversation;
      try {
        localStorage.setItem("localgpt.active", String(conversation.id));
      } catch (err) { /* ignore */ }
      el.messages.innerHTML = "";
      const messages = conversation.messages || [];
      if (messages.length) {
        el.welcome.hidden = true;
        messages.forEach(function (message) {
          el.messages.appendChild(buildMessage(message).article);
        });
      } else {
        showWelcome();
      }
      updateHeader(conversation);
      renderConversationList();
      if (opts.closeSidebar !== false) closeSidebar();
      requestAnimationFrame(function () {
        el.chatScroll.scrollTop = el.chatScroll.scrollHeight;
      });
      if (opts.focus !== false) el.input.focus();
    } catch (err) {
      toast(err.message, "error");
      if (err.status === 404) {
        try {
          await loadConversations();
        } catch (ignored) { /* ignore */ }
        resetChat();
      }
    }
  }

  async function deleteConversation(conversation) {
    if (state.streaming) return;
    const ok = await confirmDialog({
      title: "Delete conversation?",
      text: '"' + (conversation.title || "New chat") + '" and all of its messages will be permanently deleted.',
      confirmLabel: "Delete",
    });
    if (!ok) return;
    try {
      await api("/api/conversations/" + conversation.id, { method: "DELETE" });
      state.conversations = state.conversations.filter(function (item) {
        return item.id !== conversation.id;
      });
      if (state.activeId === conversation.id) resetChat();
      else renderConversationList();
      toast("Conversation deleted.", "success", 2600);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function clearActiveConversation() {
    if (state.streaming || !state.activeId) return;
    const ok = await confirmDialog({
      title: "Clear this conversation?",
      text: "All messages will be removed. The conversation itself will stay in your history.",
      confirmLabel: "Clear",
    });
    if (!ok) return;
    try {
      const conversation = await api(
        "/api/conversations/" + state.activeId + "/messages",
        { method: "DELETE" }
      );
      state.active = conversation;
      const existing = state.conversations.find(function (item) {
        return item.id === conversation.id;
      });
      if (existing) {
        existing.message_count = 0;
        existing.updated_at = conversation.updated_at;
      }
      showWelcome();
      updateHeader(conversation);
      renderConversationList();
      toast("Conversation cleared.", "success", 2600);
      el.input.focus();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Composer                                                           */
  /* ------------------------------------------------------------------ */
  function resizeInput() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 220) + "px";
    updateSendState();
  }

  function updateSendState() {
    el.send.disabled = state.streaming || !!state.creatingPromise || !el.input.value.trim();
  }

  function setStreamingUi(active) {
    state.streaming = active;
    el.app.classList.toggle("streaming", active);
    el.send.hidden = active;
    el.stop.hidden = !active;
    updateSendState();
    el.clearChat.disabled = active || !state.activeId || activeMessageCount() === 0;
  }

  function stopStreaming() {
    if (state.abortController) {
      state.abortController.abort();
    }
  }

  async function sendMessage() {
    if (state.streaming) return;
    const text = el.input.value.trim();
    if (!text) {
      el.input.focus();
      return;
    }
    if (text.length > 32000) {
      toast("Message exceeds the 32,000 character limit.", "error");
      return;
    }

    if (state.creatingPromise) {
      try {
        await state.creatingPromise;
      } catch (err) {
        toast(err.message, "error");
        return;
      }
    }

    if (!state.activeId) {
      try {
        await createConversation({ focus: false });
      } catch (err) {
        toast(err.message, "error");
        return;
      }
    }

    const conversationId = state.activeId;
    el.input.value = "";
    resizeInput();
    el.welcome.hidden = true;

    const userMessage = { role: "user", content: text, created_at: new Date().toISOString() };
    el.messages.appendChild(buildMessage(userMessage).article);
    scrollToBottom(true);

    const assistant = buildMessage(
      { role: "assistant", content: "", created_at: new Date().toISOString() },
      { streaming: true }
    );
    el.messages.appendChild(assistant.article);
    scrollToBottom(true);

    const cursor = document.createElement("span");
    cursor.className = "stream-cursor";

    setStreamingUi(true);
    const controller = new AbortController();
    state.abortController = controller;

    let buffer = "";
    let firstToken = true;
    let renderTimer = null;
    let terminal = false;
    let hadError = false;

    const renderNow = function () {
      if (!assistant.md) return;
      assistant.md.innerHTML = renderMarkdown(buffer);
      appendCursor(assistant.md, cursor);
    };

    const scheduleRender = function () {
      if (renderTimer) return;
      renderTimer = setTimeout(function () {
        renderTimer = null;
        renderNow();
        scrollToBottom(false);
      }, 45);
    };

    const finish = function () {
      if (renderTimer) {
        clearTimeout(renderTimer);
        renderTimer = null;
      }
      renderNow();
      if (cursor.parentNode) cursor.remove();
      assistant.article.classList.remove("streaming");
      if (assistant.typing && assistant.typing.parentNode) assistant.typing.remove();
      setCopyContent(assistant, buffer);
    };

    try {
      await streamChat(conversationId, text, controller.signal, function (event, data) {
        if (event === "meta") {
          if (data.conversation) {
            state.active = Object.assign({}, state.active || {}, data.conversation);
            updateHeader(state.active);
            const existing = state.conversations.find(function (item) {
              return item.id === data.conversation.id;
            });
            if (existing) {
              existing.title = data.conversation.title;
              existing.updated_at = data.conversation.updated_at;
            }
            renderConversationList();
          }
        } else if (event === "token") {
          if (firstToken) {
            firstToken = false;
            if (assistant.typing && assistant.typing.parentNode) assistant.typing.remove();
          }
          buffer += data.content || "";
          scheduleRender();
        } else if (event === "done") {
          terminal = true;
          finish();
          if (data.assistant_message) {
            setCopyContent(assistant, data.assistant_message.content || buffer);
          }
          if (data.stats) appendStats(assistant.meta, data.stats);
          if (data.conversation) {
            state.active = Object.assign({}, state.active || {}, data.conversation);
            updateHeader(state.active);
          }
          if (!buffer.trim()) {
            addErrorNotice(assistant.content, "The model returned an empty response. Try rephrasing your message.");
          }
          loadConversations().catch(function () { /* ignore */ });
        } else if (event === "error") {
          terminal = true;
          hadError = true;
          finish();
          const message = (data && data.message) || "The local model could not complete the request.";
          addErrorNotice(assistant.content, message);
          toast(message, "error");
          loadConversations().catch(function () { /* ignore */ });
        }
      });
    } catch (err) {
      finish();
      if (err && err.name === "AbortError") {
        if (!buffer.trim() && assistant.md) {
          assistant.md.innerHTML = '<p class="stopped-note">Response stopped.</p>';
        }
        const sep = document.createElement("span");
        sep.className = "dot-sep";
        const stopped = document.createElement("span");
        stopped.className = "stats";
        stopped.textContent = "stopped";
        assistant.meta.appendChild(sep);
        assistant.meta.appendChild(stopped);
        loadConversations().catch(function () { /* ignore */ });
      } else {
        hadError = true;
        addErrorNotice(assistant.content, (err && err.message) || "Unexpected error.");
        toast((err && err.message) || "Unexpected error.", "error");
        loadConversations().catch(function () { /* ignore */ });
      }
    } finally {
      if (renderTimer) {
        clearTimeout(renderTimer);
        renderTimer = null;
      }
      if (cursor.parentNode) cursor.remove();
      assistant.article.classList.remove("streaming");
      if (assistant.typing && assistant.typing.parentNode) assistant.typing.remove();
      state.abortController = null;
      setStreamingUi(false);
      if (state.active) updateHeader(state.active);
      if (!hadError) scrollToBottom(false);
      el.input.focus();
    }
  }

  /* ------------------------------------------------------------------ */
  /* Event wiring                                                       */
  /* ------------------------------------------------------------------ */
  function bindEvents() {
    el.newChat.addEventListener("click", function () {
      if (state.streaming || state.creatingPromise) return;
      createConversation({ closeSidebar: true }).catch(function (err) {
        toast(err.message, "error");
      });
    });

    el.composer.addEventListener("submit", function (event) {
      event.preventDefault();
      sendMessage();
    });

    el.input.addEventListener("input", resizeInput);
    el.input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        sendMessage();
      }
    });

    el.stop.addEventListener("click", stopStreaming);
    el.clearChat.addEventListener("click", clearActiveConversation);

    el.statusCard.addEventListener("click", function () { refreshStatus(true); });
    el.statusCard.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        refreshStatus(true);
      }
    });

    el.menuToggle.addEventListener("click", openSidebar);
    el.sidebarClose.addEventListener("click", closeSidebar);
    el.overlay.addEventListener("click", closeSidebar);

    document.querySelectorAll(".suggestion").forEach(function (button) {
      button.addEventListener("click", function () {
        el.input.value = button.dataset.prompt || "";
        resizeInput();
        el.input.focus();
      });
    });

    el.messages.addEventListener("click", function (event) {
      const codeButton = event.target.closest(".code-copy");
      if (codeButton) {
        const code = decodeURIComponent(codeButton.dataset.code || "");
        copyText(code, codeButton, null);
      }
    });

    el.modalCancel.addEventListener("click", function () { closeModal(false); });
    el.modalConfirm.addEventListener("click", function () { closeModal(true); });
    el.modal.addEventListener("click", function (event) {
      if (event.target === el.modal) closeModal(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        if (!el.modal.hidden) {
          closeModal(false);
          return;
        }
        if (el.sidebar.classList.contains("open")) {
          closeSidebar();
          return;
        }
        if (state.streaming) stopStreaming();
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        el.input.focus();
      }
    });

    window.addEventListener("online", function () { refreshStatus(true, true); });
    window.addEventListener("offline", function () {
      setStatus("offline", "You are offline", "LocalGPT still works locally");
    });

    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) refreshStatus(false, true);
    });
  }

  /* ------------------------------------------------------------------ */
  /* Init                                                               */
  /* ------------------------------------------------------------------ */
  async function init() {
    cacheDom();
    bindEvents();
    resizeInput();
    setStreamingUi(false);

    refreshStatus(false, true);
    updateRealtime();
    setInterval(function () {
      if (!document.hidden) {
        refreshStatus(false, true);
        updateRealtime();
      }
    }, 20000);

    try {
      await loadConversations();
    } catch (err) {
      toast(err.message, "error");
      showWelcome();
      updateHeader(null);
      return;
    }

    let saved = null;
    try {
      saved = Number(localStorage.getItem("localgpt.active"));
    } catch (err) {
      saved = null;
    }
    if (saved && state.conversations.some(function (item) { return item.id === saved; })) {
      await openConversation(saved, { closeSidebar: false, focus: false });
    } else {
      resetChat();
    }
    updateHeader(state.active);
    el.input.focus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
