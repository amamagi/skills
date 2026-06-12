#!/usr/bin/env python3
"""Pin GitHub Actions workflow dependencies to their commit SHAs.

Usage:
    python pin_actions.py <workflow-file>              # Pin version tags to SHAs
    python pin_actions.py <workflow-file> --update     # Update SHAs to latest
    python pin_actions.py <workflow-file> --dry-run    # Preview changes
    python pin_actions.py <dir> --all                  # Process all YAML files in directory
"""

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path


SHA_RE = re.compile(r'^[0-9a-f]{40}$')

# Matches "uses: owner/repo@ref  # optional comment"
USES_RE = re.compile(
    r'^(?P<prefix>\s+uses:\s+)'
    r'(?P<action>(?!\./)(?!docker://)(?P<owner>[A-Za-z0-9][A-Za-z0-9_.-]*)/(?P<repo>[A-Za-z0-9][A-Za-z0-9_.-]*))'
    r'@(?P<ref>[^\s#\n]+)'
    r'(?P<comment>[ \t]+#[^\n]*)?$',
    re.MULTILINE,
)


def gh_api(path):
    result = subprocess.run(
        ['gh', 'api', path],
        capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def resolve_tag_to_sha(owner, repo, ref):
    """Resolve a tag or branch to its commit SHA. Returns None on failure."""
    if SHA_RE.match(ref):
        return ref

    # Try tag ref
    data = gh_api(f'/repos/{owner}/{repo}/git/ref/tags/{ref}')
    if data and 'object' in data:
        sha = data['object']['sha']
        # Dereference annotated tags (type == "tag" points to a tag object, not a commit)
        if data['object']['type'] == 'tag':
            tag_data = gh_api(f'/repos/{owner}/{repo}/git/tags/{sha}')
            if tag_data and 'object' in tag_data:
                sha = tag_data['object']['sha']
        return sha

    # Try as branch or commit
    data = gh_api(f'/repos/{owner}/{repo}/commits/{ref}')
    if data and 'sha' in data:
        return data['sha']

    return None


def find_canonical_tag(owner, repo, commit_sha, fallback):
    """Find the most specific version tag pointing to commit_sha.

    e.g. v1 resolves to the same SHA as v1.0.146 — return v1.0.146.
    Falls back to the original ref when no better tag is found.
    """
    data = gh_api(f'/repos/{owner}/{repo}/tags?per_page=100')
    if not data:
        return fallback

    matching = [t['name'] for t in data if t.get('commit', {}).get('sha') == commit_sha]
    if not matching:
        return fallback

    # Prefer tags with more dots (v1.0.146 > v1.0 > v1)
    matching.sort(key=lambda t: (t.count('.'), len(t)), reverse=True)
    return matching[0]


def get_latest_release_sha(owner, repo):
    """Return (commit_sha, tag_name) for the latest release."""
    data = gh_api(f'/repos/{owner}/{repo}/releases/latest')
    if data and 'tag_name' in data:
        tag = data['tag_name']
        sha = resolve_tag_to_sha(owner, repo, tag)
        return sha, tag

    # Fallback: use the first entry from the tags list
    data = gh_api(f'/repos/{owner}/{repo}/tags')
    if data and len(data) > 0:
        tag = data[0]['name']
        sha = data[0].get('commit', {}).get('sha')
        if sha:
            return sha, tag

    return None, None


def process_workflow(content, update_mode):
    """Replace action references in workflow content.

    Returns (new_content, list_of_human_readable_change_messages).
    """
    messages = []

    def replace(m):
        prefix = m.group('prefix')
        action = m.group('action')
        owner = m.group('owner')
        repo = m.group('repo')
        ref = m.group('ref')

        is_sha = bool(SHA_RE.match(ref))

        if update_mode:
            new_sha, tag = get_latest_release_sha(owner, repo)
            if new_sha is None:
                messages.append(f'  WARN  cannot resolve latest: {action}@{ref}')
                return m.group(0)
            canonical = find_canonical_tag(owner, repo, new_sha, tag or ref)
            if is_sha and new_sha == ref:
                messages.append(f'  skip  already up to date: {action}')
                return m.group(0)
            old_display = ref[:12] + '...' if is_sha else ref
            verb = 'update' if is_sha else 'pin→latest'
            messages.append(f'  {verb}  {action}@{old_display} → {new_sha[:12]}... ({canonical})')
            return f'{prefix}{action}@{new_sha} # {canonical}'
        else:
            # Pin mode
            if is_sha:
                messages.append(f'  skip  already pinned: {action}@{ref[:12]}...')
                return m.group(0)
            sha = resolve_tag_to_sha(owner, repo, ref)
            if sha is None:
                messages.append(f'  WARN  cannot resolve: {action}@{ref}')
                return m.group(0)
            canonical = find_canonical_tag(owner, repo, sha, ref)
            messages.append(f'  pin   {action}@{ref} → {sha[:12]}... ({canonical})')
            return f'{prefix}{action}@{sha} # {canonical}'

    new_content = USES_RE.sub(replace, content)
    return new_content, messages


def process_file(path: Path, update_mode: bool, dry_run: bool) -> None:
    mode_label = 'update' if update_mode else 'pin'
    print(f'\n[{mode_label}] {path}')

    content = path.read_text(encoding='utf-8')
    new_content, messages = process_workflow(content, update_mode)

    for msg in messages:
        print(msg)

    if new_content == content:
        print('  (no changes)')
        return

    if dry_run:
        diff = difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f'{path} (updated)',
        )
        sys.stdout.writelines(diff)
    else:
        path.write_text(new_content, encoding='utf-8')
        print(f'  -> saved: {path}')


def main():
    parser = argparse.ArgumentParser(
        description='Pin GitHub Actions to commit SHAs',
    )
    parser.add_argument('target', help='Workflow YAML file or directory')
    parser.add_argument('--update', action='store_true',
                        help='Update existing SHA pins to the latest version')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without writing files')
    parser.add_argument('--all', action='store_true',
                        help='Process all YAML files when target is a directory')
    args = parser.parse_args()

    target = Path(args.target)

    if target.is_dir():
        if not args.all:
            print(f'Error: {target} is a directory. Add --all to process all workflow files.')
            sys.exit(1)
        files = sorted(list(target.glob('*.yml')) + list(target.glob('*.yaml')))
        if not files:
            print(f'No YAML files found in {target}')
            sys.exit(0)
        for f in files:
            process_file(f, args.update, args.dry_run)
    elif target.is_file():
        process_file(target, args.update, args.dry_run)
    else:
        print(f'Error: not found: {target}')
        sys.exit(1)


if __name__ == '__main__':
    main()
