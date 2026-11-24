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
            ours = git('show', f'HEAD:{path}', check=False)
            bp, tp = os.path.join(b, path), os.path.join(t, path)
            if ours.returncode != 0 or not os.path.exists(bp):
                left.append(path)  # added or deleted on one side: a person decides
                continue
            if not os.path.exists(tp):
                git('rm', '--quiet', path)  # upstream deleted a file the fork only perceptified
                print(f'resolved (deleted upstream): {path}')
                continue
            with open(path, 'w') as f:
                f.write(ours.stdout)
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
