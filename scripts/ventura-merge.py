#!/usr/bin/env python3
"""Fork only: merge an upstream release into ventura-support, resolving what the port's own
rules explain (docs/ventura-port.md).

Most conflicts are lines the fork changed only by running scripts/ventura-perceptify.py
(@Perceptible, WithPerceptionTracking, FrameTicker...) that upstream then edited. For each
conflicted file this merges three ways again, with the rules applied to both upstream sides:

    base     = perceptify(merge base)     ours = the fork     theirs = perceptify(upstream)

so the fork's side differs from the base only where someone edited it by hand. A file that
still conflicts is left for a person, and the script exits 1 listing it.

  ventura-merge.py <upstream commit> <message> <perceptify.py>

ventura-sync.yml passes the fork's copies from before the merge, never upstream's.
"""
import os
import subprocess
import sys
import tempfile


def git(*args, check=True, **kw):
    return subprocess.run(['git', *args], capture_output=True, text=True, check=check, **kw)


REGULAR = ('100644', '100755')


def blob_mode(commit, path):
    """The path's mode in `commit` (100644, 120000 for a symlink...), None when it isn't there."""
    out = git('ls-tree', commit, '--', path).stdout.split()
    return out[0] if out else None


def read_regular(root, path):
    """`root/path`'s text, or None unless it and every folder above it inside `root` are real (no symlinks)."""
    parts = os.path.normpath(path).split(os.sep)
    for i in range(1, len(parts) + 1):
        if os.path.islink(os.path.join(root, *parts[:i])):
            return None
    full = os.path.join(root, path)
    return open(full).read() if os.path.isfile(full) else None


def perceptified_tree(commit, perceptify, into):
    """A worktree of `commit` with the Ventura rules applied (perceptify reads the whole tree)."""
    git('worktree', 'add', '--detach', '--quiet', into, commit)
    subprocess.run([sys.executable, '-I', perceptify], cwd=into, check=True, capture_output=True)
    return into


def main():
    upstream, message, perceptify = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
    os.chdir(git('rev-parse', '--show-toplevel').stdout.strip())
    merged = git('merge', '-X', 'ignore-space-change', '--no-edit', '-m', message, upstream, check=False)
    print(merged.stdout, end='')
    if merged.returncode == 0:
        return
    conflicts = git('diff', '--name-only', '--diff-filter=U').stdout.split()
    if not conflicts:
        print(merged.stderr, file=sys.stderr)
        sys.exit(1)
    base = git('merge-base', 'HEAD', upstream).stdout.strip()
    left = []
    with tempfile.TemporaryDirectory() as tmp:
        b = perceptified_tree(base, perceptify, os.path.join(tmp, 'base'))
        t = perceptified_tree(upstream, perceptify, os.path.join(tmp, 'theirs'))
        for path in conflicts:
            modes = [blob_mode(c, path) for c in ('HEAD', base, upstream)]
            bp, tp = os.path.join(b, path), os.path.join(t, path)
            ours = git('show', f'HEAD:{path}', check=False).stdout
            if modes[0] in REGULAR and modes[1] in REGULAR and modes[2] is None and not os.path.lexists(tp):
                # Upstream deleted it: follow only if the fork never edited it by hand.
                if read_regular(b, path) == ours:
                    git('rm', '--quiet', path)
                    print(f'resolved (deleted upstream): {path}')
                else:
                    left.append(path)
                continue
            # Regular files on all three sides only: never a symlink, submodule or type change,
            # whose content merge-file would read from wherever the link points.
            if not all(m in REGULAR for m in modes) or None in (read_regular(b, path), read_regular(t, path)):
                left.append(path)
                continue
            with open(path, 'w') as f:
                f.write(ours)
            r = subprocess.run(['git', 'merge-file', '-L', 'fork', '-L', 'base', '-L', 'upstream', path, bp, tp])
            if r.returncode == 0:
                git('add', path)
                print(f'resolved: {path}')
            else:
                left.append(path)
        for w in (b, t):
            git('worktree', 'remove', '--force', w)
    if left:
        print('Still conflicted (the fork changed these by hand):')
        for path in left:
            print(f'- {path}')
        sys.exit(1)
    # The rules on the whole tree, then the commit: upstream's other new code gets them too.
    subprocess.run([sys.executable, '-I', perceptify], check=True)
    git('add', '-A')
    git('commit', '--quiet', '--no-edit', '-m', message)
    print(f'Merged with {len(conflicts)} conflicts resolved by the Ventura rules.')


if __name__ == '__main__':
    main()
