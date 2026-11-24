#!/usr/bin/env python3
"""Fork only: apply the Ventura port's Perception rules to the app (docs/ventura-port.md).

macOS 13 has no Observation, so the fork observes models through swift-perception, and a
SwiftUI view on Ventura only updates for state read inside WithPerceptionTracking. Upstream
keeps adding views; ventura-sync.yml runs this after each merge so they get the same rules:

- @Observable -> @Perceptible, @ObservationIgnored -> @PerceptionIgnored,
  @Bindable -> @Perception.Bindable, import Observation -> import Perception
- two- and no-argument .onChange closures -> Ventura's one-argument form
- Sonoma-only calls -> their stand-ins: withObservationTracking -> withPerceptionTracking,
  CADisplayLink -> FrameTicker (startFrameTicker), CASpringAnimation(perceptualDuration:) ->
  .perceptual(duration:), withAnimation(.snappy(duration:extraBounce: 0)) -> .easeOut,
  yieldActivation + activate(from:) -> bringForward(yielding:), scrollIndicatorsFlash -> ...IfAvailable;
  an .onChange closure's named old value becomes a capture of the value the body saw
- in each type that touches observable state (an observable class by name, an
  @Environment(Model.self), a bindable, AppDelegate), wrap every `some View` body and helper,
  ForEach row closure and popover/sheet content in WithPerceptionTracking { }
- standalone test harnesses (scripts/test-*.sh) that compile a file importing Perception
  source scripts/perception-test-flags.sh and pass its flags (and VenturaCompat.swift);
  Tests/*.swift get the attribute and import renames only, so locked test bodies keep their hashes

Wrapped code keeps its indentation, so upstream's later edits to those lines still merge.
Idempotent: it only adds what's missing.

  scripts/ventura-perceptify.py            rewrite Sources/Cra and CraCore in place
  scripts/ventura-perceptify.py --check    list files it would change, exit 1 if any
"""
import re
import sys


def code_mask(src):
    """Same length as src; string literals and comments replaced by spaces."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith('//', i):
            j = src.find('\n', i)
            j = n if j < 0 else j
            out.append(' ' * (j - i)); i = j
        elif src.startswith('/*', i):
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r'[^\n]', ' ', src[i:j])); i = j
        elif src.startswith('"""', i):
            j = src.find('"""', i + 3)
            j = n if j < 0 else j + 3
            out.append(re.sub(r'[^\n]', ' ', src[i:j])); i = j
        elif src[i] == '"':
            j, depth = i + 1, 0
            while j < n:
                c = src[j]
                if c == '\\' and j + 1 < n and src[j + 1] == '(':
                    depth += 1; j += 2; continue
                if c == '\\':
                    j += 2; continue
                if depth and c == '(':
                    depth += 1
                elif depth and c == ')':
                    depth -= 1
                elif not depth and c == '"':
                    break
                elif c == '\n':
                    break
                j += 1
            out.append(' ' * (j + 1 - i)); i = j + 1
        else:
            out.append(src[i]); i += 1
    return ''.join(out)[:n]


def matching_brace(mask, open_idx):
    depth = 0
    for k in range(open_idx, len(mask)):
        if mask[k] == '{':
            depth += 1
        elif mask[k] == '}':
            depth -= 1
            if depth == 0:
                return k
    raise ValueError('unbalanced braces')


def indent_of(src, idx):
    start = src.rfind('\n', 0, idx) + 1
    m = re.match(r'[ \t]*', src[start:])
    return m.group(0)


OPENERS = [
    # some View bodies and helpers (not protocol requirements, not one-liners)
    re.compile(r'(var\s+\w+\s*:\s*some\s+View|func\s+\w+[^{\n]*->\s*some\s+View)\s*\{[ \t]*\n'),
    # ForEach row closures
    re.compile(r'\bForEach\b[^\n]*\{\s*(?:[\w(), ]+\s+in)?[ \t]*\n'),
    # presentation content
    re.compile(r'\.(?:popover|sheet)\b(?=\s*\()[^\n]*\{[ \t]*\n'),
]


def wrap_one_liners(src):
    full_mask = code_mask(src)
    offsets, pos = [], 0
    for l in src.split('\n'):
        offsets.append(pos); pos += len(l) + 1
    """`ForEach(x) { BODY }` and `.popover(...) { BODY }` on one line: wrap BODY, naming $0."""
    lines = src.split('\n')
    for li, line in enumerate(lines):
        mask = code_mask(line)
        m = re.search(r'\bForEach\b(?=\s*\()|\.(?:popover|sheet)\b(?=\s*\()', mask)
        if not m or 'WithPerceptionTracking' in line or not stateful(src, full_mask, offsets[li]):
            continue
        # the trailing closure: first '{' after the call's arguments close
        k, depth = m.end(), 0
        while k < len(mask):
            c = mask[k]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            elif c == '{' and depth == 0:
                break
            k += 1
        if k >= len(mask):
            continue
        try:
            close = matching_brace(mask, k)
        except ValueError:
            continue  # multi-line: handled by wrap_all
        body = line[k + 1:close]
        pm = re.match(r'\s*((?:\w+|\([\w, ]+\))(?:\s*,\s*\w+)*)\s+in\b', body)
        if pm:
            head, rest = body[:pm.end()], body[pm.end():]
        elif '$0' in body and m.group(0) == 'ForEach':
            head, rest = ' item in', body.replace('$0', 'item')
        else:
            head, rest = '', body
        lines[li] = line[:k + 1] + head + ' WithPerceptionTracking { ' + rest.strip() + ' } ' + line[close:]
    return '\n'.join(lines)


STATE_TYPES = []


def top_level_blocks(mask):
    """(start, end) of each top-level declaration body (struct/class/extension/enum)."""
    out = []
    for m in re.finditer(r'^(?:[\w@()]+\s+)*(?:struct|class|extension|enum)\b[^{\n]*\{', mask, re.M):
        try:
            out.append((m.start(), matching_brace(mask, m.end() - 1)))
        except ValueError:
            pass
    return out


def stateful(src, mask, idx):
    for a, b in top_level_blocks(mask):
        if a <= idx <= b:
            region = mask[a:b]
            break
    else:
        return True
    if re.search(r'@Environment\(\s*\w+\.self|@(?:Perception\.)?Bindable\b|WithPerceptionTracking|\bAppDelegate\b', region):
        return True
    return any(re.search(r'\b' + t + r'\b', region) for t in STATE_TYPES)


def wrap_all(src, path):
    skipped = []
    changed = True
    done = set()
    while changed:
        changed = False
        mask = code_mask(src)
        spots = []
        for rx in OPENERS:
            for m in rx.finditer(mask):
                spots.append(m)
        spots.sort(key=lambda m: m.start())
        for m in spots:
            open_idx = m.end() - 1
            while mask[open_idx] != '{':
                open_idx -= 1
            line_end = m.end()
            # first code line of the block
            rest = src[line_end:]
            first = next((l for l in rest.split('\n') if l.strip() and not l.strip().startswith('//')), '')
            key = (src[:m.start()].count('\n'), m.group(0).strip())
            if 'WithPerceptionTracking' in first or key in done or not stateful(src, mask, m.start()):
                continue
            close = matching_brace(mask, open_idx)
            ind = indent_of(src, m.start())
            inner = ind + '    '
            new = (src[:line_end] + inner + 'WithPerceptionTracking {\n' + src[line_end:close].rstrip(' \t')
                   + inner + '}\n' + ind + src[close:])
            # keep the closing brace's own line intact
            src = new
            done.add(key)
            changed = True
            break
    mask = code_mask(src)
    for rx, what in [(re.compile(r'(var\s+body\s*:\s*some\s+View)\s*\{[^\n]*\S[^\n]*\}'), 'one-line body'),
                     (re.compile(r'\bForEach\b[^\n]*\{[^\n]*\bin\b[^\n]*\}[^\n]*$', re.M), 'one-line ForEach')]:
        for m in rx.finditer(mask):
            line = src[:m.start()].count('\n') + 1
            if 'WithPerceptionTracking' not in src.split('\n')[line - 1]:
                skipped.append(f'{path}:{line}: {what}: {src.split(chr(10))[line - 1].strip()[:100]}')
    return src, skipped


def observable_types(files):
    names = set()
    for path in files:
        text = open(path).read()
        for m in re.finditer(r'@(?:Perceptible|Observable)\b(?:\s*\n)?(?:[^\n]*\n){0,2}?[^\n]*?\bclass\s+(\w+)', text):
            names.add(m.group(1))
    return sorted(names)


DISPLAY_LINK = (r'displayLink\(target: ([^\n]+?), selector: (#selector\([^\n]*?\))\)\n'
                r'[ \t]*(?P=v)\.add\(to: \.main, forMode: \.common\)\n')


def ventura_api(src):
    """Sonoma APIs upstream keeps using, swapped for VenturaCompat.swift's stand-ins (or
    Perception's), the way the port's hand edits did."""
    src = re.sub(r'(?<![\w.])withObservationTracking\b', 'withPerceptionTracking', src)
    src = re.sub(r'\bCASpringAnimation\(perceptualDuration:\s*', 'CASpringAnimation.perceptual(duration: ', src)
    src = re.sub(r'withAnimation\(\.snappy\(duration: ([^,()]+), extraBounce: 0\)\)', r'withAnimation(.easeOut(duration: \1))', src)
    # let l = displayLink(...); l.add(...); link = l  ->  link = startFrameTicker(...)
    src = re.sub(r'^([ \t]*)let (?P<v>\w+) = ((?:[\w.]+\.)?)' + DISPLAY_LINK + r'[ \t]*([^\n=]+?) = (?P=v)\n',
                 lambda m: f'{m.group(1)}{m.group(6)} = {m.group(3)}startFrameTicker(target: {m.group(4)}, selector: {m.group(5)})\n',
                 src, flags=re.M)
    # let link = displayLink(...); link.add(...)  ->  let link = startFrameTicker(...)
    src = re.sub(r'^([ \t]*)let (?P<v>\w+) = ((?:[\w.]+\.)?)' + DISPLAY_LINK,
                 lambda m: f'{m.group(1)}let {m.group(2)} = {m.group(3)}startFrameTicker(target: {m.group(4)}, selector: {m.group(5)})\n',
                 src, flags=re.M)
    src = re.sub(r'^([ \t]*)NSApp\.yieldActivation\(to: (\w+)\)\n[ \t]*\2\.activate\(from: \.current, options: \[\]\)\n',
                 r'\1\2.bringForward(yielding: true)\n', src, flags=re.M)
    src = re.sub(r'\.scrollIndicatorsFlash\(onAppear:', '.scrollIndicatorsFlashIfAvailable(onAppear:', src)
    src = re.sub(r'\bCADisplayLink\?', '(any FrameTicker)?', src)
    src = re.sub(r'\bCADisplayLink\b', 'any FrameTicker', src)
    return src


def transform(path):
    src = open(path).read()
    if path != VENTURA_COMPAT:
        src = ventura_api(src)
    src = re.sub(r'(?<![\w.])@Bindable\b', '@Perception.Bindable', src)
    src = re.sub(r'^import Observation\n', 'import Perception\n' if 'import Perception' not in src else '', src, flags=re.M)
    src = re.sub(r'@ObservationIgnored\b', '@PerceptionIgnored', src)
    src = re.sub(r'@Observable\b', '@Perceptible', src)
    # A named old value: Ventura's closure gets only the new one, so capture the old as the body saw it.
    src = re.sub(r'(\.onChange\(of:\s*([^{\n]*?)\)\s*\{\s*)(?!_\b)(\w+)\s*,\s*(_|\w+)\s+in\b', r'\1[\3 = \2] \4 in', src)
    src = re.sub(r'(\.onChange\(of:[^{\n]*\{\s*)(?:_|\w+)\s*,\s*(_|\w+)\s+in\b', r'\1\2 in', src)
    # Sonoma's no-argument closure: Ventura's always takes the new value.
    src = re.sub(r'(\.onChange\(of:[^{\n]*\)\s*\{)(?!\s*(?:\[[^\]\n]*\]\s*)?(?:_|\w+)\s*(?:,|in\b))', r'\1 _ in', src)
    src = wrap_one_liners(src)
    src, _ = wrap_all(src, path)
    if 'import Perception' not in src and re.search(r'(?i)withPerceptionTracking|@Perception\.|@Perceptible|@PerceptionIgnored', src):
        src = 'import Perception\n' + src
    return src


VENTURA_COMPAT = 'Sources/Cra/UI/VenturaCompat.swift'
TRACKING_SHIM = 'Tests/Support/VenturaObservationTracking.swift'
COMPAT_API = re.compile(r'\b(?:startFrameTicker|FrameTicker|roundedButtonBorder|presentationBackgroundIfAvailable|scrollIndicatorsFlashIfAvailable|bringForward)\b'
                        r'|CASpringAnimation\.perceptual\b')


def harness(path):
    """A standalone test harness (swiftc on app sources) that compiles a file importing Perception
    gets scripts/perception-test-flags.sh: macOS 13 target, Perception's archive and macro, its
    stub modules built for the same target, and VenturaCompat.swift when a source needs it."""
    import glob
    src = open(path).read()
    if 'CRA_TEST_SWIFTC_FLAGS:-}' not in src:
        return src
    commands = re.findall(r'xcrun swiftc(?:[^\n]*\\\n)*[^\n]*', src)
    sources = set()
    for cmd in commands:
        for token in re.findall(r'(?:Sources|Packages|Tests)/[^\s"\\]+\.swift', cmd):
            sources.update(glob.glob(token))
    texts = [open(p).read() for p in sorted(sources)]
    if not any(re.search(r'^import Perception$', t, re.M) for t in texts):
        # No Perception, but VenturaCompat's stand-ins still have to be compiled in.
        if any(COMPAT_API.search(t) for t in texts) and VENTURA_COMPAT not in sources:
            src = re.sub(r'(\$\{CRA_TEST_SWIFTC_FLAGS:-\}(?:[^\n]*\\\n)*?[^\n]*?) -o ',
                         lambda m: m.group(1) + ' ' + VENTURA_COMPAT + ' -o ', src, count=1)
        return src
    if 'source scripts/perception-test-flags.sh' not in src:
        src = re.sub(r'^(cd "\$\(dirname "\$0"\)/\.\."\n)', r'\1source scripts/perception-test-flags.sh\n', src, count=1, flags=re.M)
    src = re.sub(r'\$\{CRA_TEST_SWIFTC_FLAGS:-\}(?! "\$\{CRA_PERCEPTION_SWIFTC_FLAGS\[@\]\}")',
                 '${CRA_TEST_SWIFTC_FLAGS:-} "${CRA_PERCEPTION_SWIFTC_FLAGS[@]}"', src)
    # Stub modules (CraCEF and the like) for the same target, or the harness can't import them.
    src = re.sub(r'^(xcrun swiftc -swift-version 5)(?![^\n]*(?:-target|CRA_PERCEPTION_SWIFTC_FLAGS))',
                 r'\1 -target "$CRA_TEST_TARGET"', src, flags=re.M)
    for extra, needed in [(VENTURA_COMPAT, any(COMPAT_API.search(t) for t in texts)),
                          (TRACKING_SHIM, any(re.search(r'(?<![\w.])withObservationTracking\s*\{', t)
                                             and 'func withObservationTracking' not in t for t in texts))]:
        if needed and extra not in sources:
            src = re.sub(r'(\$\{CRA_TEST_SWIFTC_FLAGS:-\}(?:[^\n]*\\\n)*?[^\n]*?) -o ',
                         lambda m: m.group(1) + ' ' + extra + ' -o ', src, count=1)
    return src


def test_source(path):
    """Upstream's test sources: only declarations and imports, so the test bodies (hashed in
    Tests/promises.lock) stay as written; their withObservationTracking calls get TRACKING_SHIM."""
    src = open(path).read()
    src = re.sub(r'^import Observation\n', 'import Perception\n' if 'import Perception' not in src else '', src, flags=re.M)
    src = re.sub(r'@ObservationIgnored\b', '@PerceptionIgnored', src)
    src = re.sub(r'@Observable\b', '@Perceptible', src)
    return src


def tracked(*patterns):
    """git ls-files, without symlinks: a link in upstream's tree must not make this read or
    write a file outside it."""
    import os
    import subprocess
    out = subprocess.run(['git', 'ls-files', *patterns], capture_output=True, text=True, check=True).stdout.split()
    return [p for p in out if not os.path.islink(p) and not os.path.islink(os.path.dirname(p) or '.')]


def main():
    import os
    import subprocess
    check = '--check' in sys.argv[1:]
    # The repository it's run in (CI runs a copy kept outside the checkout).
    os.chdir(subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True,
                            check=True).stdout.strip())
    files = tracked('Sources/Cra/*.swift', 'Packages/CraCore/Sources/*.swift')
    STATE_TYPES[:] = observable_types(files)
    changed = []
    for path in files:
        new = transform(path)
        if new != open(path).read():
            changed.append(path)
            if not check:
                open(path, 'w').write(new)
    tests = tracked('Tests/*.swift')
    for path in tests:
        new = test_source(path)
        if new != open(path).read():
            changed.append(path)
            if not check:
                open(path, 'w').write(new)
    # After the sources: a harness's need for Perception depends on their rewritten imports.
    scripts = tracked('scripts/*.sh', 'Tests/*.sh')
    for path in scripts:
        if path == 'scripts/perception-test-flags.sh':
            continue
        new = harness(path)
        if new != open(path).read():
            changed.append(path)
            if not check:
                open(path, 'w').write(new)
    for path in changed:
        print(('needs Ventura rules: ' if check else 'Ventura rules applied: ') + path)
    sys.exit(1 if check and changed else 0)


if __name__ == '__main__':
    main()
