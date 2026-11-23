"""Terminal server for the AI Agents app.

Every agent (Muse Code, Claude Code, Gemini CLI, Codex) and a plain shell gets its own
pseudo terminal that keeps running while the browser is closed. The page talks to it over
one WebSocket per tab through Home Assistant ingress. Only the ingress proxy may connect.
Standard library only.
"""
import base64, hashlib, json, os, re, shlex, shutil, socket, struct, subprocess, sys, tempfile, threading, time, urllib.request, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote

try:
    import fcntl, pty, signal, termios
except ImportError:  # lets the module be imported on Windows for syntax checks
    pty = None

APP = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get('HOME', '/data')
WD = os.environ.get('AGENT_WD', '/homeassistant')
SKILLS = os.environ.get('SKILLS', '/opt/skills')
VENDOR = os.environ.get('VENDOR', '/opt/vendor')
PORT = int(os.environ.get('PORT', '8099'))
ALLOWED = {'172.30.32.2', '127.0.0.1', '::1'}
BUFFER = 1_000_000          # bytes of scrollback kept per tab for reconnects
MAX_FRAME = 16 * 1024 * 1024  # largest WebSocket message accepted from the browser
QUIET = 1.0                 # seconds after a browser attaches during which its input is dropped
WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
CDN = {
    'xterm.css': 'https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.css',
    'xterm.js': 'https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.js',
    'addon-fit.js': 'https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.js',
    'addon-web-links.js': 'https://cdn.jsdelivr.net/npm/@xterm/addon-web-links@0.11.0/lib/addon-web-links.js',
}

AGENTS = {
    'muse': {
        'name': 'Muse Code', 'bin': 'muse', 'by': 'Meta',
        'resume': ['resume', '--last'], 'login': ['login'], 'compact': '/compact',
        'install': 'curl -fsSL https://dev.meta.ai/install.sh | bash',
        'docs': 'https://dev.meta.ai/docs/muse-code/',
        'hint': 'Sign in with your Meta account the first time (or set meta_api_key in the app options).',
    },
    'claude': {
        'name': 'Claude Code', 'bin': 'claude', 'by': 'Anthropic',
        'resume': ['--continue'], 'login': None, 'compact': None,  # has its own idle compaction
        'install': 'curl -fsSL https://claude.ai/install.sh | bash',
        'docs': 'https://docs.claude.com/en/docs/claude-code/overview',
        'hint': 'On first start choose "Claude account with subscription", open the link, sign in and paste the code back here. Type /login to switch account.',
    },
    'gemini': {
        'name': 'Gemini CLI', 'bin': 'gemini', 'by': 'Google',
        'resume': ['--resume', 'latest'], 'login': None, 'compact': '/compress',
        'install': 'npm install -g @google/gemini-cli@latest',
        'docs': 'https://geminicli.com/docs/',
        'hint': 'On first start choose "Login with Google", open the link, sign in and paste the authorization code back here.',
    },
    'codex': {
        'name': 'Codex', 'bin': 'codex', 'by': 'OpenAI',
        'resume': ['resume', '--last'], 'login': ['login', '--device-auth'], 'compact': '/compact',
        'install': 'npm install -g @openai/codex@latest',
        'docs': 'https://developers.openai.com/codex/cli',
        'hint': 'Press "Sign in" to log in with ChatGPT using a device code (the normal browser login cannot reach this container).',
    },
}
# Where each agent keeps its sign-in, and the env vars that make a sign-in unnecessary
CREDENTIALS = {
    'muse': (['.config/muse/auth.json'], ['META_API_KEY']),
    'claude': (['.claude/.credentials.json'], ['ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN']),
    'gemini': (['.gemini/oauth_creds.json'], ['GEMINI_API_KEY', 'GOOGLE_API_KEY']),
    'codex': (['.codex/auth.json'], ['OPENAI_API_KEY']),
}
# Where the newest version is published
LATEST = {
    'muse': ('https://api.meta.ai/muse-code/channels/muse-stable', 'version'),
    'claude': ('https://registry.npmjs.org/@anthropic-ai/claude-code/latest', 'version'),
    'gemini': ('https://registry.npmjs.org/@google/gemini-cli/latest', 'version'),
    'codex': ('https://registry.npmjs.org/@openai/codex/latest', 'version'),
}
# Settings made on the settings page live in /data/settings.json and win over the app options
SETTINGS_FILE = os.path.join(DATA, 'settings.json')
TOKEN_FILE = os.path.join(DATA, 'ha_user_token')
OLD_TOKEN_FILE = os.path.join(DATA, '.claude', 'secrets', 'ha_user_token')   # before 0.3.0
NUMBERS = {'autocompact_tokens': ('AUTOCOMPACT_TOKENS', 2_000_000), 'idle_compact_minutes': ('IDLE_COMPACT_MINUTES', 1440)}
TEXTS = ['muse_args', 'claude_args', 'gemini_args', 'codex_args', 'ha_url']
SECRETS = {'anthropic_api_key': 'ANTHROPIC_API_KEY', 'gemini_api_key': 'GEMINI_API_KEY',
           'openai_api_key': 'OPENAI_API_KEY', 'meta_api_key': 'META_API_KEY'}


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding='utf8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def number(key):
    env, top = NUMBERS[key]
    v = load_settings().get(key)
    if v is None:
        v = os.environ.get(env)
    try:
        return min(top, max(0, int(v or 0)))
    except (TypeError, ValueError):
        return 0


def COMPACT():   # compact the conversation at this many tokens (0 = each agent's own default)
    return number('autocompact_tokens')


def IDLE():      # compact after this many quiet minutes, while the prompt cache is still warm
    return number('idle_compact_minutes')


_ha_url = []


def default_ha_url():
    """Address of Home Assistant Core inside the app network, with the port it really listens on."""
    if _ha_url:
        return _ha_url[0]
    try:
        req = urllib.request.Request('http://supervisor/core/info',
                                     headers={'Authorization': 'Bearer ' + os.environ.get('SUPERVISOR_TOKEN', '')})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r).get('data') or {}
        url = f"{'https' if d.get('ssl') else 'http'}://homeassistant:{int(d.get('port') or 8123)}"
        _ha_url.append(url)  # only a real answer is kept; after a failure the next call asks again
        return url
    except Exception as e:
        print('could not read the Home Assistant port, using 8123:', e, flush=True)
        return 'http://homeassistant:8123'


def ha_token():
    if not os.path.exists(TOKEN_FILE) and os.path.exists(OLD_TOKEN_FILE):
        try:
            os.replace(OLD_TOKEN_FILE, TOKEN_FILE)
        except OSError:
            pass
    try:
        with open(TOKEN_FILE, encoding='utf8') as f:
            return f.read().strip()
    except OSError:
        return ''


CONTEXT = {'muse': 1_007_997, 'gemini': 1_048_576}   # context windows, for agents that take a fraction


def compact_args(aid):
    COMPACT_ = COMPACT()
    if not COMPACT_:
        return []
    if aid == 'muse':
        return ['-c', f'context_compaction.soft_threshold={min(0.95, COMPACT_ / CONTEXT["muse"]):.3f}']
    if aid == 'codex':
        return ['-c', f'model_auto_compact_token_limit={COMPACT_}']
    return []  # Claude Code: env var in child_env(); Gemini CLI: settings.json in configure_gemini()


def configure_gemini():
    COMPACT_ = COMPACT()
    if not COMPACT_ or 'gemini' not in ENABLED:
        return
    p = os.path.join(DATA, '.gemini', 'settings.json')
    try:
        with open(p, encoding='utf8') as f:
            d = json.load(f)
    except FileNotFoundError:
        d = {}
    except (OSError, ValueError):
        print('not touching', p, '(not valid JSON)', flush=True)
        return
    frac = round(min(0.95, COMPACT_ / CONTEXT['gemini']), 3)
    if d.get('model', {}).get('compressionThreshold') != frac:
        d.setdefault('model', {})['compressionThreshold'] = frac
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf8') as f:
            json.dump(d, f, indent=2)


ENABLED = [a for a in (os.environ.get('AGENTS') or ' '.join(AGENTS)).split() if a in AGENTS] or list(AGENTS)
TABS = ENABLED + ['shell']


def args_for(aid):
    v = load_settings().get(aid + '_args')
    try:
        return shlex.split(v if isinstance(v, str) else os.environ.get('ARGS_' + aid.upper(), ''))
    except ValueError:
        return []


def child_env():
    env = dict(os.environ)
    env.update(TERM='xterm-256color', COLORTERM='truecolor', LANG='C.UTF-8', HOME=DATA,
               NO_BROWSER='true', HA_URL='http://supervisor/core', FORCE_HYPERLINK='1',
               IS_SANDBOX='1',  # the container is the sandbox; lets Claude Code skip permissions as root
               PYTHONDONTWRITEBYTECODE='1')  # no __pycache__ folders in the config or app folders
    st = load_settings()
    for k, e in SECRETS.items():  # keys from the settings page win over the app options
        if st.get(k):
            env[e] = st[k]
    tok = ha_token()
    if tok:  # full-access token: ha-api and ha-ws use it instead of the Supervisor token
        url = (st.get('ha_url') or default_ha_url()).rstrip('/')
        env['HA_USER_TOKEN'], env['HA_DIRECT_URL'] = tok, url
        if url.startswith('https://homeassistant:'):  # the certificate is made for the public name, not this one
            env['HA_DIRECT_INSECURE'] = '1'
    if COMPACT() >= 100_000:
        env['CLAUDE_CODE_AUTO_COMPACT_WINDOW'] = str(COMPACT())
    if IDLE():  # Claude Code compacts idle conversations itself (about an hour, before its cache expires)
        env['CLAUDE_CODE_IDLE_COMPACT_MIN_TOKENS'] = '100000'
    env.pop('PORT', None)
    return env


# ---------------------------------------------------------------- versions and skills

_versions, _vlock = {}, threading.Lock()


def signed_in(aid):
    files, env = CREDENTIALS[aid]
    st = load_settings()
    if any(os.environ.get(e) or st.get(k) for k, e in SECRETS.items() if e in env) or any(os.environ.get(e) for e in env):
        return True
    for f in files:
        p = os.path.join(DATA, f)
        try:
            if os.path.getsize(p) > 2:
                return True
        except OSError:
            pass
    if aid == 'claude':  # older Claude Code versions keep the account in ~/.claude.json
        try:
            with open(os.path.join(DATA, '.claude.json'), encoding='utf8') as f:
                return '"oauthAccount"' in f.read()
        except OSError:
            pass
    return False


_latest = {}


def check_latest():
    """Looks up the newest published version of each agent every 6 hours."""
    while True:
        for aid in ENABLED:
            url, key = LATEST[aid]
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'ai-agents-app', 'Accept': 'application/json'})
                with urllib.request.urlopen(req, timeout=20) as r:
                    _latest[aid] = str(json.load(r).get(key) or '')
            except Exception as e:
                print('version check failed for', aid, e, flush=True)
        time.sleep(6 * 3600)


def vtuple(s):
    """'Muse Code 1.4.24 (1.4.24-R9131.1)' -> (1,4,24,9131,1); '2.1.3 (Claude Code)' -> (2,1,3). Takes the most detailed match."""
    best = None
    for m in re.finditer(r'(\d+)\.(\d+)\.(\d+)(?:-R(\d+)(?:\.(\d+))?)?', s or ''):
        t = tuple(int(x) for x in m.groups() if x is not None)
        if best is None or len(t) > len(best):
            best = t
    return best


def update_available(aid, installed):
    """The newest version as text when it is newer than the installed one, else None."""
    new, old = vtuple(_latest.get(aid)), vtuple(installed)
    if not new or not old:
        return None
    n = min(len(new), len(old))
    return _latest[aid] if new[:n] > old[:n] else None


def which(aid):
    return shutil.which(AGENTS[aid]['bin'], path=child_env()['PATH'])


def version(aid, fresh=False):
    with _vlock:
        hit = _versions.get(aid)
        if hit and not fresh:
            if time.time() - hit[1] > 300:  # stale: answer now, refresh in the background
                _versions[aid] = (hit[0], time.time())
                threading.Thread(target=version, args=(aid, True), daemon=True).start()
            return hit[0]
    v = ''
    exe = which(aid)
    if exe:
        try:
            out = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=20, env=child_env(),
                                 stdin=subprocess.DEVNULL)
            v = (out.stdout or out.stderr).strip().splitlines()[0][:80] if (out.stdout or out.stderr).strip() else 'installed'
        except Exception:
            v = 'installed'
    with _vlock:
        _versions[aid] = (v, time.time())
    return v


def rules_text():
    try:
        with open(os.path.join(APP, 'rules.md'), encoding='utf8') as f:
            text = f.read()
    except OSError:
        text = ''
    names = []
    for n in sorted(os.listdir(SKILLS)) if os.path.isdir(SKILLS) else []:
        p = os.path.join(SKILLS, n, 'SKILL.md')
        if os.path.isfile(p):
            desc = ''
            with open(p, encoding='utf8', errors='replace') as f:
                m = re.search(r'^description:\s*(.+)$', f.read(4000), re.M)
                desc = m.group(1).strip().strip('"\'') if m else ''
            names.append(f'- `{p}`: {desc[:300]}')
    return text.replace('{{SKILLS}}', '\n'.join(names) or '- (none installed)')


MARK = '<!-- managed by the AI Agents app; delete this line to keep your own version -->'


def write_managed(path, text):
    try:
        if os.path.exists(path):
            with open(path, encoding='utf8', errors='replace') as f:
                if MARK not in f.read():
                    return  # the user took the file over
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf8') as f:
            f.write(MARK + '\n' + text)
    except OSError as e:
        print('could not write', path, e, flush=True)


def sync_skills():
    """Give every agent the same house rules, skills and settings."""
    try:
        configure_gemini()
    except Exception as e:
        print('gemini settings failed', e, flush=True)
    text = rules_text()
    write_managed(os.path.join(DATA, '.claude', 'CLAUDE.md'), text)
    write_managed(os.path.join(DATA, '.codex', 'AGENTS.md'), text)
    write_managed(os.path.join(DATA, '.gemini', 'GEMINI.md'), text)
    write_managed(os.path.join(DATA, '.config', 'muse', 'AGENTS.md'), text)
    if not os.path.isdir(SKILLS):
        return
    skills = [n for n in sorted(os.listdir(SKILLS)) if os.path.isfile(os.path.join(SKILLS, n, 'SKILL.md'))]
    for root in ('.claude/skills', '.codex/skills', '.gemini/skills'):
        d = os.path.join(DATA, root)
        os.makedirs(d, exist_ok=True)
        for n in skills:
            link = os.path.join(d, n)
            try:
                if os.path.islink(link):
                    os.remove(link)
                if not os.path.exists(link):
                    os.symlink(os.path.join(SKILLS, n), link)
            except OSError as e:
                print('skill link failed', link, e, flush=True)
    muse = which('muse') if 'muse' in ENABLED else None
    if muse:
        for n in skills:
            try:
                subprocess.run([muse, 'skills', 'install', os.path.join(SKILLS, n), '--scope', 'user', '--force'],
                               capture_output=True, timeout=60, env=child_env(), stdin=subprocess.DEVNULL, cwd=DATA)
            except Exception as e:
                print('muse skills install failed', n, e, flush=True)
    print('skills ready:', ', '.join(skills), flush=True)


# ---------------------------------------------------------------- WebSocket (RFC 6455, minimal)

class WS:
    def __init__(self, sock, rfile):
        self.sock, self.rfile, self.lock = sock, rfile, threading.Lock()

    def send(self, data, binary=False):
        if isinstance(data, str):
            data = data.encode('utf8')
        n = len(data)
        head = bytes([0x82 if binary else 0x81])
        if n < 126:
            head += bytes([n])
        elif n < 65536:
            head += bytes([126]) + struct.pack('>H', n)
        else:
            head += bytes([127]) + struct.pack('>Q', n)
        with self.lock:
            self.sock.sendall(head + data)

    def send_json(self, o):
        self.send(json.dumps(o))

    def _exact(self, n):
        b = self.rfile.read(n)
        if b is None or len(b) < n:
            raise EOFError
        return b

    def recv(self):
        """Returns the next text/binary message, or None when the socket closes."""
        parts, kind = [], None
        try:
            while True:
                b0, b1 = self._exact(2)
                op, n = b0 & 0x0F, b1 & 0x7F
                if n == 126:
                    n = struct.unpack('>H', self._exact(2))[0]
                elif n == 127:
                    n = struct.unpack('>Q', self._exact(8))[0]
                if n > MAX_FRAME:
                    return None
                mask = self._exact(4) if b1 & 0x80 else None
                data = self._exact(n) if n else b''
                if mask and n:
                    k = (mask * (n // 4 + 1))[:n]
                    data = (int.from_bytes(data, 'big') ^ int.from_bytes(k, 'big')).to_bytes(n, 'big')
                if op == 8:
                    try:
                        self.send_raw(0x88, b'')
                    except OSError:
                        pass
                    return None
                if op == 9:
                    self.send_raw(0x8A, data)
                    continue
                if op == 10:
                    continue
                if op in (1, 2):
                    kind = op
                parts.append(data)
                if b0 & 0x80:
                    msg = b''.join(parts)
                    return msg.decode('utf8', 'replace') if kind == 1 else msg
        except (EOFError, OSError, ValueError):
            return None

    def send_raw(self, b0, data):
        with self.lock:
            self.sock.sendall(bytes([b0, len(data)]) + data)


# ---------------------------------------------------------------- terminals

class Tab:
    def __init__(self, tid):
        self.tid = tid
        self.pid = self.fd = None
        self.code = None
        self.label = ''
        self.buf = bytearray()
        self.clients = set()
        self.lock = threading.Lock()
        self.size = (120, 32)
        self.started_once = False
        self.started_at = 0.0
        self.fallback = None
        self.activity = time.monotonic()  # last input or output
        self.turns = 0                    # messages sent since the last compaction
        self.typing = False               # text typed but not sent yet

    def running(self):
        return self.pid is not None and self.code is None

    def state(self):
        return {'t': 'state', 'running': self.running(), 'code': self.code, 'label': self.label}

    def broadcast(self, data, binary=True):
        for c in list(self.clients):
            try:
                c.send(data, binary)
            except OSError:
                self.clients.discard(c)

    def note(self, text):
        b = ('\r\n\x1b[2m' + text + '\x1b[0m\r\n').encode()
        with self.lock:
            self.buf += b
        self.broadcast(b)

    def start(self, argv, label, fallback=None):
        if pty is None:
            raise RuntimeError('terminals need Linux')
        self.stop()
        env = child_env()
        pid, fd = pty.fork()
        if pid == 0:  # child
            try:
                os.chdir(WD if os.path.isdir(WD) else DATA)
                os.execvpe(argv[0], argv, env)
            finally:
                os._exit(127)
        with self.lock:
            self.pid, self.fd, self.code, self.label, self.buf = pid, fd, None, label, bytearray()
        self.started_once = True
        self.started_at = time.monotonic()
        self.turns, self.typing = 0, False
        self.fallback = fallback
        self.resize(*self.size)
        self.broadcast(json.dumps({'t': 'reset'}), binary=False)
        self.broadcast(json.dumps(self.state()), binary=False)
        threading.Thread(target=self._read, args=(pid, fd), daemon=True).start()

    def _read(self, pid, fd):
        while True:
            try:
                b = os.read(fd, 65536)
            except OSError:
                b = b''
            if not b:
                break
            self.activity = time.monotonic()
            with self.lock:
                self.buf += b
                if len(self.buf) > BUFFER:
                    del self.buf[:len(self.buf) - BUFFER // 2]
            self.broadcast(b)
        try:
            _, st = os.waitpid(pid, 0)
            code = os.waitstatus_to_exitcode(st)
        except Exception:
            code = -1
        try:
            os.close(fd)
        except OSError:
            pass
        if self.pid == pid:
            self.code = code
            label = self.label
            fb = self.fallback
            if fb and code != 0 and time.monotonic() - self.started_at < 8:
                # nothing to resume (first run, or the conversation is gone): start a new one instead
                self.fallback = None
                try:
                    self.start(fb[0], fb[1])
                    return
                except Exception as e:
                    print('fallback start failed', e, flush=True)
            self.note(f'[{label} ended with exit code {code}]')
            self.broadcast(json.dumps(self.state()), binary=False)
            if label.startswith('install'):
                after_install(self.tid)

    def write(self, data):
        text = data.decode('utf8', 'replace') if isinstance(data, bytes) else data
        self.activity = time.monotonic()
        if '\r' in text or '\n' in text:
            self.typing, self.turns = False, self.turns + 1
        elif text and not text.startswith('\x1b') and text.isprintable():
            self.typing = True
        if self.running():
            try:
                os.write(self.fd, data if isinstance(data, bytes) else data.encode('utf8'))
            except OSError:
                pass

    def resize(self, cols, rows):
        cols, rows = max(20, min(int(cols), 500)), max(5, min(int(rows), 200))
        self.size = (cols, rows)
        if self.running():
            try:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
            except OSError:
                pass

    def nudge(self):
        """Makes full-screen programs redraw for a newly attached browser."""
        if self.running():
            c, r = self.size
            self.resize(c, r - 1)
            time.sleep(0.05)
            self.resize(c, r)

    def stop(self):
        pid = self.pid
        if not self.running():
            return
        for sig, wait in ((signal.SIGHUP, 1.5), (signal.SIGTERM, 1.5), (signal.SIGKILL, 1.0)):
            try:
                os.killpg(pid, sig)
            except OSError:
                try:
                    os.kill(pid, sig)
                except OSError:
                    pass
            end = time.time() + wait
            while time.time() < end and self.code is None:
                time.sleep(0.05)
            if self.code is not None:
                return


tabs = {t: Tab(t) for t in TABS}


def idle_compactor():
    """Sends an agent its compact command after IDLE quiet minutes, so the summary is made while the cache is warm.
    Only when something was said since the last compaction and nothing is half typed."""
    while True:
        time.sleep(30)
        now = time.monotonic()
        if not IDLE():
            continue
        for tid in ENABLED:
            t, cmd = tabs[tid], AGENTS[tid].get('compact')
            if not cmd or not t.running() or t.turns == 0 or t.typing or now - t.activity < IDLE() * 60:
                continue
            print(f'idle for {IDLE()} min: sending {cmd} to {tid}', flush=True)
            t.write(cmd)
            time.sleep(0.4)
            t.write('\r')
            t.turns = 0


def after_install(aid):
    if aid in AGENTS:
        version(aid, fresh=True)
        threading.Thread(target=sync_skills, daemon=True).start()


def command(tid, action):
    """argv and label for a tab action."""
    if tid == 'shell':
        return ['bash'], 'shell'
    a = AGENTS[tid]
    if action == 'install':
        script = (f'set -o pipefail; echo "Installing {a["name"]} ..."; {a["install"]}; rc=$?; echo; '
                  f'if [ $rc -eq 0 ]; then echo "Done. Press Start to run {a["name"]}."; '
                  f'else echo "Install failed (exit code $rc)."; fi; exit $rc')
        return ['bash', '-c', script], 'install'
    exe = which(tid)
    if not exe:
        raise ValueError(f'{a["name"]} is not installed yet')
    if action == 'login' and a['login']:
        return [exe] + a['login'], 'sign in'
    if action == 'login':  # these agents ask for a sign-in themselves on first start
        action = 'start'
    extra = a['resume'] if action == 'resume' else []
    return [exe] + args_for(tid) + compact_args(tid) + extra, a['name']


def tab_info(tid):
    t = tabs[tid]
    if tid == 'shell':
        return {'id': 'shell', 'name': 'Shell', 'by': '', 'installed': True, 'version': 'bash', 'running': t.running(),
                'label': t.label, 'login': False, 'started': t.started_once, 'hint': 'A root shell in /homeassistant. ha-api and ha-ws talk to Home Assistant.'}
    a = AGENTS[tid]
    v = version(tid)
    return {'id': tid, 'name': a['name'], 'by': a['by'], 'installed': bool(v), 'version': v, 'running': t.running(),
            'label': t.label, 'login': bool(v) and not signed_in(tid), 'update': bool(v) and update_available(tid, v) or None,
            'hint': a['hint'], 'docs': a['docs'], 'started': t.started_once}


# ---------------------------------------------------------------- HTTP

FILES_DIR = os.environ.get('FILES_DIR', '/share/ai_agents_files')
IMG_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
             '.svg': 'image/svg+xml', '.pdf': 'application/pdf', '.txt': 'text/plain; charset=utf-8', '.md': 'text/plain; charset=utf-8'}


def files_path(name):
    """Safe path inside FILES_DIR for a plain file name, or None."""
    name = os.path.basename(name or '')
    if not name or name.startswith('.') or name.endswith('.part'):
        return None
    return os.path.join(FILES_DIR, name)


def files_list():
    os.makedirs(FILES_DIR, exist_ok=True)
    out = []
    for n in os.listdir(FILES_DIR):
        p = os.path.join(FILES_DIR, n)
        if os.path.isfile(p) and not n.startswith('.') and not n.endswith('.part'):
            st = os.stat(p)
            out.append({'name': n, 'size': st.st_size, 'mtime': int(st.st_mtime), 'image': os.path.splitext(n)[1].lower() in IMG_TYPES and not n.lower().endswith(('.txt', '.md'))})
    return sorted(out, key=lambda f: -f['mtime'])


def zip_names(qs):
    """(name, path) for each existing file named in the query (name=a&name=b), without duplicates."""
    out, seen = [], set()
    for n in parse_qs(qs).get('name', []):
        p = files_path(n)
        if p and os.path.isfile(p) and p not in seen:
            seen.add(p)
            out.append((os.path.basename(p), p))
    return out


def mask(v):
    return ('…' + v[-4:]) if len(v) > 8 else '••••'


def settings_view():
    st = load_settings()
    out = {'defaults': {}, 'values': {}, 'secrets': {}}
    for k, (e, _) in NUMBERS.items():  # values: what is set on the settings page; defaults: the app options
        out['defaults'][k] = os.environ.get(e, '')
        out['values'][k] = st.get(k, '')
    for k in TEXTS:
        out['defaults'][k] = os.environ.get('ARGS_' + k[:-5].upper(), '') if k.endswith('_args') else default_ha_url()
        out['values'][k] = st[k] if isinstance(st.get(k), str) else ''
    for k, e in SECRETS.items():
        v = st.get(k) or os.environ.get(e, '')
        out['secrets'][k] = {'set': bool(v), 'hint': mask(v) if v else '', 'source': 'settings' if st.get(k) else ('options' if v else '')}
    t = ha_token()
    out['secrets']['ha_token'] = {'set': bool(t), 'hint': mask(t) if t else '', 'source': 'file' if t else ''}
    out['enabled'] = ENABLED
    return out


def save_settings(d):
    """Numbers and texts replace the stored value; a secret is only changed when a new one is sent
    (a value of null clears it). Applies to conversations started afterwards."""
    st = load_settings()
    for k, (_, top) in NUMBERS.items():
        if k in d and (d[k] is None or str(d[k]).strip() == ''):
            st.pop(k, None)  # empty: use the app option again
        elif k in d:
            v = int(d[k])
            if not 0 <= v <= top:
                raise ValueError(f'{k} must be between 0 and {top}')
            st[k] = v
    for k in TEXTS:
        if k in d and (d[k] is None or not str(d[k]).strip()):
            st.pop(k, None)  # empty: use the app option (or the detected address) again
        elif k in d:
            v = str(d[k]).strip()
            if k == 'ha_url' and v and not re.fullmatch(r'https?://[\w.\-]+(:\d+)?', v.rstrip('/')):
                raise ValueError('ha_url must look like http://192.168.1.10')
            st[k] = v
    for k in SECRETS:
        if k in d:
            if d[k] is None:
                st.pop(k, None)
            elif str(d[k]).strip():
                st[k] = str(d[k]).strip()
    if 'ha_token' in d:
        v = d['ha_token']
        if v is None:
            try:
                os.remove(TOKEN_FILE)
            except OSError:
                pass
        elif str(v).strip():
            v = str(v).strip()
            if not re.fullmatch(r'[\w.\-]{20,}', v):
                raise ValueError('that does not look like a Home Assistant token')
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(v)
    tmp = SETTINGS_FILE + '.part'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf8') as f:
        json.dump(st, f, indent=2)
    os.replace(tmp, SETTINGS_FILE)
    threading.Thread(target=configure_gemini, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def reply(self, code, data, ctype='application/json; charset=utf-8', extra=None):
        b = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode('utf8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(b)
        except (BrokenPipeError, ConnectionResetError):  # the browser already went away
            self.close_connection = True

    def allowed(self):
        if self.client_address[0] not in ALLOWED:
            self.reply(403, {'error': 'only through Home Assistant'})
            return False
        if (self.headers.get('Sec-Fetch-Site') or '').lower() == 'cross-site':
            # the panel is always same-origin with Home Assistant; another web site must not drive the terminals
            self.reply(403, {'error': 'cross-site request refused'})
            return False
        return True

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def do_GET(self):
        if not self.allowed():
            return
        path, _, qs = self.path.partition('?')
        q = dict(x.split('=', 1) for x in qs.split('&') if '=' in x)
        if path in ('/', '/index.html'):
            with open(os.path.join(APP, 'index.html'), 'rb') as f:
                return self.reply(200, f.read(), 'text/html; charset=utf-8')
        if path.startswith('/vendor/'):
            name = os.path.basename(path)
            p = os.path.join(VENDOR, name)
            if os.path.isfile(p) and os.path.getsize(p) > 0:
                with open(p, 'rb') as f:
                    ct = 'text/css' if name.endswith('.css') else 'text/javascript'
                    return self.reply(200, f.read(), ct + '; charset=utf-8', {'Cache-Control': 'max-age=86400'})
            if name in CDN:
                return self.reply(302, b'', 'text/plain', {'Location': CDN[name]})
            return self.reply(404, {'error': 'not found'})
        if path == '/api/files':
            return self.reply(200, files_list())
        if path == '/api/file':
            p = files_path((parse_qs(qs).get('name') or [''])[0])
            if p and os.path.isfile(p):
                ct = IMG_TYPES.get(os.path.splitext(p)[1].lower(), 'application/octet-stream')
                with open(p, 'rb') as f:
                    return self.reply(200, f.read(), ct, {'Content-Disposition': "inline; filename*=UTF-8''" + quote(os.path.basename(p)),
                                                           'Content-Security-Policy': "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"})
            return self.reply(404, {'error': 'not found'})
        if path == '/api/files/zip':
            return self.send_zip(qs)
        if path == '/api/settings':
            return self.reply(200, settings_view())
        if path == '/api/tabs':
            return self.reply(200, [tab_info(t) for t in TABS])
        if path == '/ws':
            return self.websocket(q.get('tab', ''))
        self.reply(404, {'error': 'unknown'})

    def do_HEAD(self):  # lets the page check that a zip download is possible before it starts one
        if not self.allowed():
            return
        path, _, qs = self.path.partition('?')
        names = zip_names(qs) if path == '/api/files/zip' else None
        self.send_response(200 if names else 404)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def send_zip(self, qs):
        """The selected files of the Files tab as one zip, built in a temporary file and streamed."""
        names = zip_names(qs)
        if not names:
            return self.reply(404, {'error': 'no such files'})
        with tempfile.TemporaryFile(dir='/tmp' if os.path.isdir('/tmp') else None) as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
                for n, p in names:
                    z.write(p, n)
            size = tmp.tell()
            tmp.seek(0)
            self.send_response(200)
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Length', str(size))
            self.send_header('Content-Disposition', 'attachment; filename="ai_agents_files.zip"')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            try:
                shutil.copyfileobj(tmp, self.wfile, 65536)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

    def do_POST(self):
        if not self.allowed():
            return
        if self.path.split('?')[0] == '/api/settings':
            try:
                save_settings(self.body())
            except Exception as e:
                return self.reply(400, {'error': str(e)})
            return self.reply(200, settings_view())
        if self.path.startswith('/api/files/'):
            action, _, qs = self.path[len('/api/files/'):].partition('?')
            p = files_path((parse_qs(qs).get('name') or [''])[0])
            if not p:
                return self.reply(400, {'error': 'bad name'})
            os.makedirs(FILES_DIR, exist_ok=True)
            if action == 'upload':
                n, limit = int(self.headers.get('Content-Length') or 0), 200 * 1024 * 1024
                if n > limit:
                    return self.reply(413, {'error': 'file too large (max 200 MB)'})
                with open(p + '.part', 'wb') as f:
                    left = n
                    while left > 0:
                        chunk = self.rfile.read(min(65536, left))
                        if not chunk:
                            break
                        f.write(chunk)
                        left -= len(chunk)
                if left > 0:  # the browser went away halfway
                    os.remove(p + '.part')
                    return self.reply(400, {'error': 'upload was interrupted'})
                os.replace(p + '.part', p)
                return self.reply(200, {'ok': True, 'path': p})
            if action == 'delete':
                try:
                    os.remove(p)
                except OSError:
                    pass
                return self.reply(200, {'ok': True})
            return self.reply(404, {'error': 'unknown'})
        m = re.fullmatch(r'/api/tab/(\w+)/(\w+)', self.path.split('?')[0])
        if not m or m.group(1) not in tabs:
            return self.reply(404, {'error': 'unknown'})
        tid, action = m.groups()
        try:
            d = self.body()
        except Exception:
            d = {}
        t = tabs[tid]
        if d.get('cols') and d.get('rows'):
            t.size = (int(d['cols']), int(d['rows']))
        try:
            if action == 'stop':
                t.stop()
            elif action in ('start', 'resume', 'login', 'install'):
                argv, label = command(tid, action)
                t.start(argv, label, fallback=command(tid, 'start') if action == 'resume' else None)
            else:
                return self.reply(404, {'error': 'unknown action'})
        except Exception as e:
            return self.reply(400, {'error': str(e)})
        return self.reply(200, tab_info(tid))

    def websocket(self, tid):
        t = tabs.get(tid)
        key = self.headers.get('Sec-WebSocket-Key')
        if not t or not key or 'websocket' not in (self.headers.get('Upgrade') or '').lower():
            return self.reply(400, {'error': 'expected a websocket for a known tab'})
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept)
        self.end_headers()
        self.wfile.flush()
        self.close_connection = True
        sock = self.connection
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ws = WS(sock, self.rfile)
        with t.lock:
            replay = bytes(t.buf)
            ws.send_json({'t': 'reset'})
            ws.send_json(t.state())
            if replay:
                ws.send_json({'t': 'replay'})
                ws.send(replay, binary=True)
                ws.send_json({'t': 'live'})
            t.clients.add(ws)
        attached = time.monotonic()

        def quiet():
            # A freshly loaded page answers old terminal queries and may send stray keys; drop its input for
            # the first second. A program started after the page attached is live, so its answers pass.
            return time.monotonic() - attached < QUIET and t.started_at < attached
        try:
            first = True
            while True:
                msg = ws.recv()
                if msg is None:
                    break
                if isinstance(msg, bytes):
                    if not quiet():
                        t.write(msg)
                    continue
                try:
                    o = json.loads(msg)
                except ValueError:
                    continue
                if o.get('t') == 'i':
                    if not quiet():
                        t.write(o.get('d', ''))
                elif o.get('t') == 'r':
                    t.resize(o.get('c', 120), o.get('r', 32))
                    if first:
                        first = False
                        t.nudge()
                elif o.get('t') == 'ping':
                    ws.send_json({'t': 'pong'})
        finally:
            t.clients.discard(ws)


if __name__ == '__main__':
    os.makedirs(DATA, exist_ok=True)
    threading.Thread(target=sync_skills, daemon=True).start()
    threading.Thread(target=check_latest, daemon=True).start()
    threading.Thread(target=idle_compactor, daemon=True).start()
    for a in ENABLED:
        threading.Thread(target=version, args=(a,), daemon=True).start()
    print(f'AI Agents listening on {PORT} (tabs: {", ".join(TABS)})', flush=True)
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
