"""Generate Windows and iOS entries through the pinned official WebToApp tool.

Windows output adapts only generated launchers, never upstream tracked files.
No site HTML, browser storage, signing secrets, or telemetry is packaged.
"""
import argparse
import hashlib
import json
import plistlib
import subprocess
import sys
import zipfile
from pathlib import Path

PIN = '3704633018bfef5fbf2783e3b59870eac8bc109c'
URL = 'https://duf5391-ux.github.io/ielts-learning/'

VBS = r'''Option Explicit
Dim ws, fs, here, browser, candidate, paths, url, mode, sc
Set ws = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
here = fs.GetParentFolderName(WScript.ScriptFullName)
url = "https://duf5391-ux.github.io/ielts-learning/"
mode = ""
If WScript.Arguments.Count > 0 Then mode = WScript.Arguments(0)
If mode = "--shortcut" Then
  Set sc = ws.CreateShortcut(ws.SpecialFolders("Desktop") & "\雅思学习册.lnk")
  sc.TargetPath = ws.ExpandEnvironmentStrings("%SystemRoot%\System32\wscript.exe")
  sc.Arguments = Chr(34) & here & "\IELTS.vbs" & Chr(34)
  sc.WorkingDirectory = here
  sc.IconLocation = here & "\icon.ico"
  sc.Description = "雅思学习册"
  sc.Save
  WScript.Echo "已创建雅思学习册桌面快捷方式。请保留当前文件夹。"
  WScript.Quit 0
End If
browser = ""
paths = Array("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", _
  "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe", _
  "%LocalAppData%\Microsoft\Edge\Application\msedge.exe", _
  "%ProgramFiles%\Google\Chrome\Application\chrome.exe", _
  "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe", _
  "%LocalAppData%\Google\Chrome\Application\chrome.exe")
For Each candidate In paths
  candidate = ws.ExpandEnvironmentStrings(candidate)
  If fs.FileExists(candidate) Then
    browser = candidate
    Exit For
  End If
Next
If mode = "--check" Then
  If browser = "" Then
    WScript.Echo "Default browser fallback: " & url
  Else
    WScript.Echo "Browser: " & browser
    WScript.Echo "URL: " & url
  End If
  WScript.Quit 0
End If
If browser <> "" Then
  ws.Run Chr(34) & browser & Chr(34) & " --app=" & Chr(34) & url & Chr(34) & " --new-window --window-size=1280,900", 1, False
Else
  ws.Run Chr(34) & url & Chr(34), 1, False
End If
'''

README = '''雅思学习册 · Windows

1. 完整解压此 ZIP，并将文件夹放在希望长期保留的位置。
2. 双击「开始学习.cmd」进入学习册。
3. 可选：双击「创建桌面快捷方式.cmd」。此后从桌面进入，请保留解压文件夹。

这是浏览器应用窗口启动器，优先使用已安装的 Edge，其次 Chrome；没有时打开默认浏览器。
它不安装额外浏览器，不需要管理员权限。网页由云端运行，内容更新无需重装。
个人记录保存在所用浏览器中；切换浏览器或设备请使用学习册的备份导出/导入。
需联网。网址：https://duf5391-ux.github.io/ielts-learning/
基于 shiaho777/WebToApp (MIT) 的 Windows 输出适配，许可证随包附带。
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--dependency-dir', type=Path)
    args = parser.parse_args()
    upstream, out = args.upstream.resolve(), args.output.resolve()
    head = subprocess.run(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
    assert head == PIN, 'Upstream revision changed'
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    assert config['id'] == 'ieltsstudy' and config['url'] == URL
    icon = (args.config.parent / 'icon.png').read_bytes()
    if args.dependency_dir:
        sys.path.insert(0, str(args.dependency_dir.resolve()))
    sys.path.insert(0, str(upstream))
    from server.engine.distiller import Distiller
    distiller = Distiller()
    out.mkdir(parents=True, exist_ok=True)
    distiller._build_windows(out, config, icon, URL)
    distiller._build_ios(out, config, icon)
    profile_path = out / 'ios.mobileconfig'
    profile = plistlib.loads(profile_path.read_bytes())
    assert profile['PayloadType'] == 'Configuration'
    assert len(profile['PayloadContent']) == 1
    clip = profile['PayloadContent'][0]
    assert clip['PayloadType'] == 'com.apple.webClip.managed'
    assert clip['URL'] == URL and clip['FullScreen'] and clip['IsRemovable']
    assert not profile['PayloadRemovalDisallowed']
    assert clip['Icon'] == icon
    allowed = {'FullScreen', 'IgnoreManifestScope', 'IsRemovable', 'Label', 'Icon',
               'PayloadDisplayName', 'PayloadIdentifier', 'PayloadType', 'PayloadUUID', 'PayloadVersion', 'URL'}
    assert set(clip) <= allowed, 'Unexpected profile payload capabilities'
    license_data = (upstream / 'LICENSE').read_bytes()
    with zipfile.ZipFile(out / 'windows.zip') as archive:
        ico = next(archive.read(n) for n in archive.namelist() if n.endswith('/icon.ico'))
    prefix = 'IELTS-Study/'
    with zipfile.ZipFile(out / 'windows.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(prefix + 'IELTS.vbs', VBS.replace('\n', '\r\n').encode('utf-16'))
        archive.writestr(prefix + '开始学习.cmd', '@echo off\r\nstart "" wscript.exe "%~dp0IELTS.vbs"\r\n')
        archive.writestr(prefix + '创建桌面快捷方式.cmd', '@echo off\r\nwscript.exe "%~dp0IELTS.vbs" --shortcut\r\n')
        archive.writestr(prefix + '使用说明.txt', README.encode('utf-8-sig'))
        archive.writestr(prefix + 'icon.ico', ico)
        archive.writestr(prefix + 'icon.png', icon)
        archive.writestr(prefix + 'LICENSE-WebToApp.txt', license_data)
    report = {'url': URL, 'upstream': 'https://github.com/shiaho777/WebToApp', 'upstream_commit': PIN,
              'ios': {'type': 'unsigned removable Web Clip profile', 'payload_count': 1,
                      'profile_uuid': profile['PayloadUUID'], 'full_screen': True},
              'windows': {'type': 'Edge/Chrome app-mode launcher with default-browser fallback',
                          'requires_admin': False, 'utf16_vbs': True},
              'device_installation_tested': False,
              'files': [{'name': name, 'bytes': (out/name).stat().st_size,
                         'sha256': hashlib.sha256((out/name).read_bytes()).hexdigest()}
                        for name in ['windows.zip', 'ios.mobileconfig']]}
    (out / 'desktop-ios-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
