"""Verify every byte of the already published learning site before embedding it."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE_COMMIT = '1dd86b0486750bad7a5ab04ecfd9f654a052ae0a'
HOME_SHA = 'ee2cc2b72e9ca3f4e0a6c23d4ad3fc40af697b9f3c3a59e576480c34c743a9f8'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('publication', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.publication / 'manifest.json').read_text(encoding='utf-8-sig'))
    assert manifest['published_html_sha256'] == HOME_SHA
    root = (args.publication / 'site').resolve()
    assert not args.destination.exists(), 'Use a fresh bundle destination'
    total = 0
    for item in manifest['files']:
        path = (root / item['path']).resolve()
        assert path.is_relative_to(root) and path.is_file()
        data = path.read_bytes()
        assert len(data) == item['bytes'], item['path']
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['path']
        total += len(data)
    assert total == manifest['total_bytes']
    shutil.copytree(root, args.destination)
    report = {'commit': SOURCE_COMMIT, 'homepage_sha256': HOME_SHA,
              'files': len(manifest['files']), 'bytes': total, 'all_file_hashes_verified': True}
    (args.destination.parent / 'bundle-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    if sys.platform == 'darwin':
        assets = args.destination.parent / 'Assets.xcassets'
        iconset = assets / 'AppIcon.appiconset'
        iconset.mkdir(parents=True, exist_ok=True)
        subprocess.run(['sips', '-z', '1024', '1024', str(args.destination.parent.parent / 'config/icon.png'),
                        '--out', str(iconset / 'AppIcon.png')], check=True)
        (assets / 'Contents.json').write_text(json.dumps({'info': {'author':'xcode','version':1}}))
        (iconset / 'Contents.json').write_text(json.dumps({'images':[
            {'idiom':'universal','platform':'ios','size':'1024x1024','filename':'AppIcon.png'}],
            'info':{'author':'xcode','version':1}}))

if __name__ == '__main__':
    main()
