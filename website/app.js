/**
 * Cord Language — Interactive Showcase & Simulator
 * High-craft, reactive client-side scripting.
 */

document.addEventListener('DOMContentLoaded', () => {
  initInstallTabs();
  initCopyButtons();
  initDiscordSimulator();
  initCodeShowcase();
  initReplTerminal();
  initMobileMenu();
});

/* -------------------------------------------------------------
 * 1. Install Command Selector & Clipboard
 * ----------------------------------------------------------- */
function initInstallTabs() {
  const tabs = document.querySelectorAll('.install-tab');
  const cmdText = document.getElementById('installCmdText');

  const commands = {
    pip: 'pip install cord-lang',
    pipx: 'pipx run cord-lang init my-bot',
    docker: 'docker run -it --rm -v $(pwd):/app cord-lang run bot.cord'
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.cmd;
      if (cmdText && commands[target]) {
        cmdText.textContent = commands[target];
      }
    });
  });
}

function initCopyButtons() {
  const copyButtons = document.querySelectorAll('[data-copy-target]');

  copyButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      const targetId = btn.getAttribute('data-copy-target');
      const targetEl = document.getElementById(targetId);
      if (!targetEl) return;

      const textToCopy = targetEl.textContent.trim();
      try {
        await navigator.clipboard.writeText(textToCopy);
        const originalText = btn.innerHTML;
        btn.classList.add('copied');
        btn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg> Copied!
        `;
        setTimeout(() => {
          btn.innerHTML = originalText;
          btn.classList.remove('copied');
        }, 2000);
      } catch (err) {
        console.error('Failed to copy text: ', err);
      }
    });
  });
}

/* -------------------------------------------------------------
 * 2. Interactive Discord Simulator & Cord Inspector
 * ----------------------------------------------------------- */
function initDiscordSimulator() {
  // Simulator State
  const state = {
    verified: false,
    selectedRole: null,
    diceRoll: 18,
    warnCount: 1,
    history: []
  };

  // DOM Elements
  const verifyBtn = document.getElementById('simVerifyBtn');
  const diceBtn = document.getElementById('simDiceBtn');
  const warnBtn = document.getElementById('simWarnBtn');
  const selectTrigger = document.getElementById('simSelectTrigger');
  const selectOptions = document.getElementById('simSelectOptions');
  const selectLabel = document.getElementById('simSelectLabel');
  const embedDesc = document.getElementById('simEmbedDesc');
  const embedFieldRole = document.getElementById('simFieldRole');
  const embedFieldStatus = document.getElementById('simFieldStatus');
  const ephemeralArea = document.getElementById('simEphemeralNotice');
  const inspectorCode = document.getElementById('inspectorCode');
  const inspectorLog = document.getElementById('inspectorLog');

  // Simulator Cord code blocks
  const cordSnippets = {
    default: `
<span class="kw">bot</span> <span class="str">"InteractiveServerBot"</span>

<span class="kw">command</span> menu:
    <span class="kw">reply</span> <span class="str">"Server Portal Controls"</span> <span class="kw">with</span>:
        <span class="kw">button</span> <span class="str">"verify_btn"</span>:
            label <span class="str">"Verify Member"</span>
            style <span class="str">"success"</span>
        <span class="kw">button</span> <span class="str">"dice_btn"</span>:
            label <span class="str">"Roll d20"</span>
            style <span class="str">"primary"</span>
        <span class="kw">button</span> <span class="str">"warn_btn"</span>:
            label <span class="str">"Issue Warn"</span>
            style <span class="str">"danger"</span>
        <span class="kw">select</span> <span class="str">"role_select"</span>:
            placeholder <span class="str">"Select specialization..."</span>
`,
    verify: `
<div class="code-active-line"><span class="kw">when</span> <span class="kw">button</span> <span class="str">"verify_btn"</span> <span class="kw">is clicked</span>:
    <span class="kw">if</span> <span class="kw">not</span> author.has_role(<span class="str">"Verified"</span>):
        author.add_role(<span class="str">"Verified"</span>)
        <span class="kw">reply</span> <span class="str">"✅ Verification complete! Welcome to the server."</span>
    <span class="kw">else</span>:
        <span class="kw">reply</span> <span class="str">"ℹ️ You are already verified, {author.name}!"</span></div>
`,
    dice: `
<div class="code-active-line"><span class="kw">when</span> <span class="kw">button</span> <span class="str">"dice_btn"</span> <span class="kw">is clicked</span>:
    roll = random(1, 20)
    <span class="kw">reply</span> <span class="str">"🎲 {author.name} rolled a **{roll}**!"</span></div>
`,
    warn: `
<div class="code-active-line"><span class="kw">when</span> <span class="kw">button</span> <span class="str">"warn_btn"</span> <span class="kw">is clicked</span>:
    <span class="kw">require</span> <span class="kw">permission</span> moderate_members
    store.warns = store.warns + 1
    <span class="kw">reply</span> <span class="str">"⚠️ Warning issued. Server total: {store.warns}"</span></div>
`,
    role: `
<div class="code-active-line"><span class="kw">when</span> <span class="kw">select</span> <span class="str">"role_select"</span> <span class="kw">is chosen</span>:
    author.set_role(selected)
    <span class="kw">reply</span> <span class="str">"Assigned specialization: **{selected}**"</span></div>
`
  };

  function updateInspector(snippetKey, logMessage) {
    if (inspectorCode && cordSnippets[snippetKey]) {
      inspectorCode.innerHTML = cordSnippets.default + cordSnippets[snippetKey];
    }
    if (inspectorLog) {
      inspectorLog.textContent = `[EVENT] ${new Date().toLocaleTimeString()} → ${logMessage}`;
      inspectorLog.style.color = '#34d399';
    }
  }

  // 1. Verify Button
  if (verifyBtn) {
    verifyBtn.addEventListener('click', () => {
      state.verified = !state.verified;
      if (embedFieldStatus) {
        embedFieldStatus.textContent = state.verified ? 'Verified Citizen ✅' : 'Guest (Unverified)';
        embedFieldStatus.style.color = state.verified ? '#34d399' : '#f8fafc';
      }
      if (ephemeralArea) {
        ephemeralArea.style.display = 'flex';
        ephemeralArea.innerHTML = state.verified 
          ? `👁️ <em>Only you can see this</em> — <strong>Verified!</strong> Member role assigned.`
          : `👁️ <em>Only you can see this</em> — Verification revoked.`;
      }
      verifyBtn.textContent = state.verified ? '✓ Verified' : '✅ Verify Member';
      updateInspector('verify', `button "verify_btn" handled (verified=${state.verified}) in 1.2ms`);
    });
  }

  // 2. Dice Roll Button
  if (diceBtn) {
    diceBtn.addEventListener('click', () => {
      state.diceRoll = Math.floor(Math.random() * 20) + 1;
      if (ephemeralArea) {
        ephemeralArea.style.display = 'flex';
        ephemeralArea.innerHTML = `🎲 <strong>D20 Roll:</strong> You rolled a natural <strong>${state.diceRoll}</strong>! ${state.diceRoll === 20 ? '🔥 CRITICAL HIT!' : ''}`;
      }
      updateInspector('dice', `button "dice_btn" dispatched -> random(1, 20) = ${state.diceRoll}`);
    });
  }

  // 3. Warn Button
  if (warnBtn) {
    warnBtn.addEventListener('click', () => {
      state.warnCount += 1;
      if (embedDesc) {
        embedDesc.innerHTML = `Interactive server portal. Active warnings recorded: <strong style="color: #f43f5e;">${state.warnCount}</strong>`;
      }
      if (ephemeralArea) {
        ephemeralArea.style.display = 'flex';
        ephemeralArea.innerHTML = `⚠️ <em>Audit log written</em> — Warning #${state.warnCount} recorded into SQLite store.`;
      }
      updateInspector('warn', `button "warn_btn" executed -> store.warns updated to ${state.warnCount}`);
    });
  }

  // 4. Select Menu
  if (selectTrigger && selectOptions) {
    selectTrigger.addEventListener('click', () => {
      selectOptions.classList.toggle('open');
    });

    const options = selectOptions.querySelectorAll('.discord-select-option');
    options.forEach(opt => {
      opt.addEventListener('click', () => {
        const value = opt.getAttribute('data-value');
        const title = opt.querySelector('.discord-option-title').textContent;
        state.selectedRole = title;
        
        if (selectLabel) selectLabel.textContent = title;
        if (embedFieldRole) embedFieldRole.textContent = title;
        selectOptions.classList.remove('open');

        if (ephemeralArea) {
          ephemeralArea.style.display = 'flex';
          ephemeralArea.innerHTML = `🌟 Assigned specialization to <strong>${title}</strong>!`;
        }
        updateInspector('role', `select "role_select" option "${value}" committed to state`);
      });
    });

    // Close select on outside click
    document.addEventListener('click', (e) => {
      if (!selectTrigger.contains(e.target) && !selectOptions.contains(e.target)) {
        selectOptions.classList.remove('open');
      }
    });
  }
}

/* -------------------------------------------------------------
 * 3. Code Showcase Gallery
 * ----------------------------------------------------------- */
function initCodeShowcase() {
  const tabs = document.querySelectorAll('.showcase-tab');
  const codePanel = document.getElementById('showcaseCode');
  const metaTitle = document.getElementById('showcaseMetaTitle');
  const metaDesc = document.getElementById('showcaseMetaDesc');
  const metaFeatures = document.getElementById('showcaseMetaFeatures');

  const examples = {
    components: {
      title: "UI Components & Select Menus",
      desc: "Create rich interactive buttons, dropdowns, and modals directly in your reply statements without building subclassed View objects.",
      features: [
        "First-class button and select declarations",
        "Direct reactive 'when button is clicked' event listeners",
        "Zero interaction tokens or ephemeral boilerplate",
        "Automatic component cleanup and disable handling"
      ],
      code: `<span class="kw">bot</span> <span class="str">"ComponentDemo"</span>

<span class="kw">config</span>:
    prefix = <span class="str">"!"</span>

<span class="kw">command</span> menu:
    <span class="kw">reply</span> <span class="str">"Choose your role and actions below:"</span> <span class="kw">with</span>:
        <span class="kw">button</span> <span class="str">"verify_btn"</span>:
            label <span class="str">"Verify Account"</span>
            style <span class="str">"success"</span>
            emoji <span class="str">"✅"</span>
        <span class="kw">button</span> <span class="str">"docs_btn"</span>:
            label <span class="str">"Read Docs"</span>
            style <span class="str">"link"</span>
            url <span class="str">"https://cord-lang.org"</span>
        <span class="kw">select</span> <span class="str">"role_select"</span>:
            placeholder <span class="str">"Select your specialization..."</span>
            min_values <span class="num">1</span>
            max_values <span class="num">1</span>
            <span class="kw">option</span> <span class="str">"engineer"</span>:
                label <span class="str">"Software Engineer"</span>
                emoji <span class="str">"💻"</span>
            <span class="kw">option</span> <span class="str">"designer"</span>:
                label <span class="str">"UI/UX Designer"</span>
                emoji <span class="str">"🎨"</span>

<span class="kw">when</span> <span class="kw">button</span> <span class="str">"verify_btn"</span> <span class="kw">is clicked</span>:
    <span class="kw">reply</span> <span class="str">"Verification complete! Welcome to the server, {author.name}."</span>

<span class="kw">when</span> <span class="kw">select</span> <span class="str">"role_select"</span> <span class="kw">is chosen</span>:
    <span class="kw">reply</span> <span class="str">"Updated role preference to **{selected}** for {author.name}!"</span>`
    },
    moderation: {
      title: "Native Moderation Primitives",
      desc: "Built-in statements for bans, kicks, timeouts, and unbans. Cord handles audit logs, permission verification, and durations natively.",
      features: [
        "Native 'ban', 'kick', 'timeout', 'unban' statements",
        "Declarative 'require permission' security gates",
        "Human duration syntax ('10m', '2h', '7d')",
        "Automatic audit-log reason attachment"
      ],
      code: `<span class="kw">bot</span> <span class="str">"ModShield"</span>

<span class="kw">config</span>:
    prefix = <span class="str">"!"</span>
    activity = <span class="str">"guarding servers"</span>

<span class="kw">when</span> someone joins:
    <span class="kw">send</span> <span class="chan">#welcome</span> <span class="str">"Welcome {member.mention}! Please respect our rules."</span>

<span class="kw">command</span> warn(target: Member, reason = <span class="str">"No reason provided"</span>):
    <span class="kw">require</span> <span class="kw">permission</span> moderate_members
    <span class="kw">cooldown</span> <span class="num">3s</span> <span class="kw">per</span> user

    <span class="kw">if</span> target.is_bot:
        <span class="kw">reply</span> <span class="str">"❌ You cannot warn a bot."</span>
        <span class="kw">return</span>

    store.warns[target.id] = (store.warns[target.id] <span class="kw">or</span> <span class="num">0</span>) + <span class="num">1</span>

    <span class="kw">reply</span> <span class="kw">embed</span>:
        title <span class="str">"⚠️ Member Warned"</span>
        description <span class="str">"{target.mention} received a warning from {author.mention}."</span>
        color <span class="str">"#F59E0B"</span>
        field <span class="str">"Reason"</span> reason inline=<span class="kw">false</span>

<span class="kw">command</span> mute(target: Member, duration: Duration = <span class="num">10m</span>, reason = <span class="str">"Rule violation"</span>):
    <span class="kw">require</span> <span class="kw">permission</span> moderate_members
    <span class="fn">timeout</span> target <span class="kw">for</span> duration reason=reason
    <span class="kw">reply</span> <span class="str">"🔇 Timed out {target.name} for {duration}."</span>

<span class="kw">command</span> banish(target: Member, reason = <span class="str">"Severe violation"</span>):
    <span class="kw">require</span> <span class="kw">permission</span> ban_members
    <span class="fn">ban</span> target reason=reason
    <span class="kw">reply</span> <span class="str">"🔨 Successfully banned {target.name}."</span>`
    },
    fetch: {
      title: "Built-in Async HTTP & Fetch",
      desc: "Connect your Discord bot to REST APIs, webhooks, and third-party services in two lines without installing requests, aiohttp, or handling sessions.",
      features: [
        "Native fetch() and http.get / post / delete",
        "Direct dot-syntax JSON parsing (res.quote, res.items[0])",
        "Automatic timeout handling and error encapsulation",
        "Non-blocking async runtime under the hood"
      ],
      code: `<span class="kw">bot</span> <span class="str">"CryptoBot"</span>

<span class="kw">config</span>:
    prefix = <span class="str">"!"</span>

<span class="kw">command</span> btc:
    res = <span class="fn">fetch</span>(<span class="str">"https://api.coindesk.com/v1/bpi/currentprice.json"</span>)
    <span class="kw">if</span> res.ok:
        usd_rate = res.bpi.USD.rate
        <span class="kw">reply</span> <span class="kw">embed</span>:
            title <span class="str">"Bitcoin Price Index"</span>
            description <span class="str">"1 BTC = **\${usd_rate}** USD"</span>
            color <span class="str">"#F7931A"</span>
            footer <span class="str">"Updated: {res.time.updated}"</span>
    <span class="kw">else</span>:
        <span class="kw">reply</span> <span class="str">"Could not retrieve crypto price data."</span>

<span class="kw">command</span> post_log(event_name: String):
    payload = {<span class="str">"event"</span>: event_name, <span class="str">"author"</span>: author.name}
    res = <span class="fn">http.post</span>(<span class="str">"https://httpbin.org/post"</span>, json=payload)
    <span class="kw">reply</span> <span class="str">"Logged event with status: {res.status}"</span>`
    },
    store: {
      title: "Persistent SQLite Store",
      desc: "Cord embeds a zero-config, persistent SQLite document and key-value store. Save user balances, levels, and server configs with zero database administration.",
      features: [
        "No database setup, connection pools, or SQL migrations",
        "Persists across bot restarts and machine reboots",
        "Nested maps, lists, and numbers supported out of the box",
        "Safe atomic writes with file locking"
      ],
      code: `<span class="kw">bot</span> <span class="str">"EconomyBot"</span>

<span class="kw">command</span> daily:
    <span class="kw">cooldown</span> <span class="num">24h</span> <span class="kw">per</span> user
    current = store.balances.get(author.id, <span class="num">0</span>)
    store.balances[author.id] = current + <span class="num">100</span>
    <span class="kw">reply</span> <span class="str">"💰 Claimed daily reward! New balance: **{store.balances[author.id]} coins**"</span>

<span class="kw">command</span> balance(target: Member = <span class="kw">null</span>):
    user = target <span class="kw">or</span> author
    coins = store.balances.get(user.id, <span class="num">0</span>)
    <span class="kw">reply</span> <span class="str">"{user.mention} holds **{coins} coins**."</span>`
    },
    tasks: {
      title: "Automated Background Tasks",
      desc: "Run scheduled background tasks, server status monitors, and recurring announcements without dealing with asyncio.sleep loops or cron daemons.",
      features: [
        "Natural interval syntax: 'every 30m', 'every 2h'",
        "Independent non-blocking execution thread",
        "Direct access to bot channels (#announcements)",
        "Zero task lifecycle boilerplate"
      ],
      code: `<span class="kw">bot</span> <span class="str">"ServerStatus"</span>

<span class="kw">task</span> health_check <span class="kw">every</span> <span class="num">15m</span>:
    res = <span class="fn">http.get</span>(<span class="str">"https://api.myserver.com/health"</span>)
    <span class="kw">if</span> <span class="kw">not</span> res.ok:
        <span class="kw">send</span> <span class="chan">#dev-alerts</span> <span class="str">"🚨 API Server returned unhealthy status: {res.status}"</span>

<span class="kw">task</span> daily_quote <span class="kw">every</span> <span class="num">24h</span>:
    q = <span class="fn">fetch</span>(<span class="str">"https://dummyjson.com/quotes/random"</span>)
    <span class="kw">if</span> q.ok:
        <span class="kw">send</span> <span class="chan">#general</span> <span class="kw">embed</span>:
            title <span class="str">"Daily Thought"</span>
            description <span class="str">"\"{q.quote}\" — **{q.author}**"</span>
            color <span class="str">"#38BDF8"</span>`
    }
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const key = tab.dataset.showcase;
      const data = examples[key];
      if (!data) return;

      if (codePanel) codePanel.innerHTML = `<pre><code>${data.code}</code></pre>`;
      if (metaTitle) metaTitle.textContent = data.title;
      if (metaDesc) metaDesc.textContent = data.desc;
      if (metaFeatures) {
        metaFeatures.innerHTML = data.features.map(f => `<li>${f}</li>`).join('');
      }
    });
  });
}

/* -------------------------------------------------------------
 * 4. Interactive Browser Mini-REPL Shell
 * ----------------------------------------------------------- */
function initReplTerminal() {
  const screen = document.getElementById('termScreen');
  const chips = document.querySelectorAll('.term-chip');
  if (!screen) return;

  const responses = {
    'ping': {
      cmd: 'command ping: reply "Pong! {bot.latency}ms"',
      output: `✓ Command 'ping' registered [Slash + Prefix]\n→ Evaluated: Pong! 16ms (latency verified)`
    },
    'fetch': {
      cmd: 'res = fetch("https://httpbin.org/status/200")',
      output: `res = Response(status=200, ok=true, headers={'content-type': 'application/json'})\n→ res.ok => true`
    },
    'store': {
      cmd: 'store.user_coins = 500; store.get("user_coins")',
      output: `[SQLite Store] Key 'user_coins' persisted to disk (.cord_store.db)\n→ 500`
    },
    'check': {
      cmd: 'cord check bot.cord',
      output: `Parsing bot.cord ...\n[AST] 1 bot declaration, 3 commands, 2 event handlers.\n✓ Success: No syntax or type errors found in 48 lines.`
    },
    'docker': {
      cmd: 'cord docker --compose',
      output: `Generated Dockerfile (multi-stage python:3.12-slim)\nGenerated docker-compose.yml (with restart policy and .env injection)\n✓ Ready to deploy with 'docker compose up -d'`
    }
  };

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const action = chip.dataset.action;
      const data = responses[action];
      if (!data) return;

      appendReplOutput(data.cmd, data.output);
    });
  });

  function appendReplOutput(cmd, output) {
    const entry = document.createElement('div');
    entry.className = 'term-entry';
    entry.style.marginTop = '12px';
    entry.innerHTML = `
      <div class="term-line"><span class="term-prompt">cord &gt;</span> <span class="term-cmd">${escapeHtml(cmd)}</span></div>
      <div class="term-output"><pre style="margin: 0; font-family: inherit;">${escapeHtml(output)}</pre></div>
    `;
    screen.appendChild(entry);
    screen.scrollTop = screen.scrollHeight;
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

/* -------------------------------------------------------------
 * 5. Mobile Navigation
 * ----------------------------------------------------------- */
function initMobileMenu() {
  const toggle = document.querySelector('.mobile-toggle');
  const navLinks = document.querySelector('.nav-links');

  if (toggle && navLinks) {
    toggle.addEventListener('click', () => {
      const isVisible = navLinks.style.display === 'flex';
      navLinks.style.display = isVisible ? 'none' : 'flex';
      navLinks.style.flexDirection = 'column';
      navLinks.style.position = 'absolute';
      navLinks.style.top = 'var(--header-height)';
      navLinks.style.left = '0';
      navLinks.style.width = '100%';
      navLinks.style.background = 'var(--bg-secondary)';
      navLinks.style.padding = '20px';
      navLinks.style.borderBottom = '1px solid var(--border-default)';
    });
  }
}
