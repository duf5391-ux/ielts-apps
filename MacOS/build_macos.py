"""Run the pinned upstream macOS builder in a stdlib-only adapter.

Only the existing macOS methods/helpers are compiled from the upstream AST;
unrelated web-server and Android imports are unnecessary for this package.
The default app reuses upstream's Chromium/default-browser launch branch.
"""
import argparse,ast,hashlib,html,io,json,plistlib,re,shlex,struct,subprocess,tempfile,zipfile
from pathlib import Path
from types import SimpleNamespace
from PIL import Image

PIN='3704633018bfef5fbf2783e3b59870eac8bc109c'
URL='https://duf5391-ux.github.io/ielts-learning/'
HELPER_SHA='4f81479e8a52bc7eded279246ed1e202ea7801f7466ad97406a7fd9b05b8fa09'
sha=lambda data:hashlib.sha256(data).hexdigest()
README='''雅思学习册 · macOS

1. 解压后，优先打开「雅思学习册.app」。它复用同作者工具的浏览器应用模式：已安装Chrome/Edge等浏览器时打开独立窗口，否则打开默认浏览器。
2. 也可双击「在浏览器打开.webloc」，从普通浏览器进入同一学习册。
3. 「雅思学习册-原生受限备用.app」是原作者WKWebView薄窗口，macOS 11起；已知缺少文件选择、确认框及下载处理，不适合备份导入导出、完整口语练习。不要把它作为主要学习入口。

两个入口的记录可能分别存储；浏览器模式使用所选浏览器记录，原生窗口使用自己的WebView存储。没有跨设备云同步，切换前用浏览器完成备份；录音单独下载。
网址固定为 https://duf5391-ux.github.io/ielts-learning/ ，内容随网站更新。需要联网，不包含整套离线材料。

这是基于 shiaho777/WebToApp 固定3704633源码的本地组装包。包未Apple Developer ID签名/公证，未在Mac实机安装或验证Gatekeeper。请按macOS正常安全提示操作，不需要关闭系统安全保护。
麦克风、音频、下载/导入、重启恢复仍需Mac实机验证；静态生成和检查不等于实机验收。
许可证随包附带，完整网页修复已在隔离浏览器测试。GitHub Pages在部分大陆网络仍可能连接超时。
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    upstream=a.upstream.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    head=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip();assert head==PIN
    config=json.loads(a.config.read_text(encoding='utf-8-sig'));assert config['url']==URL and config['id']=='ieltsstudy'
    source_path=upstream/'server/engine/distiller.py';source=source_path.read_text(encoding='utf8');tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Distiller')
    names={'_safe_fs_name','_xml_esc','_bundle_id_part'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'_build_macos','_png_to_icns'}]
    assert len(nodes)==3 and len(methods)==2
    js=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_MACOS_WEBVIEW_APP_JS' for t in n.targets))
    env={'re':re,'html':html,'shlex':shlex,'zipfile':zipfile,'struct':struct,'Path':Path,'_MACOS_TEMPLATE_DIR':upstream/'server/engine/macos_template','_MACOS_HELPER_NAME':'wta_webview','_MACOS_WEBVIEW_APP_JS':js}
    exec(compile(ast.Module(body=nodes+methods,type_ignores=[]),str(source_path),'exec'),env)
    icon_stream=io.BytesIO();Image.open(a.config.parent/'icon.png').convert('RGBA').resize((256,256)).save(icon_stream,format='PNG');icon=icon_stream.getvalue()
    builder=SimpleNamespace();builder._png_to_icns=lambda png:env['_png_to_icns'](builder,png)
    with tempfile.TemporaryDirectory(prefix='ielts-macos-') as scratch:
        env['_build_macos'](builder,Path(scratch),config,icon,URL)
        with zipfile.ZipFile(Path(scratch)/'macos.zip') as original: raw={n:original.read(n) for n in original.namelist()}
    original_root=next(iter(raw)).split('/')[0];prefix=original_root+'/Contents/'
    original_launcher=raw[prefix+'MacOS/launcher'].decode();helper=raw[prefix+'MacOS/wta_webview'];assert sha(helper)==HELPER_SHA
    assert helper[:4]==b'\xca\xfe\xba\xbe' and struct.unpack('>I',helper[4:8])[0]==2
    cpus=[struct.unpack('>I',helper[8+i*20:12+i*20])[0] for i in range(2)];assert set(cpus)=={0x1000007,0x100000c}
    # Keep exactly the upstream environment + existing Chromium/browser branch.
    main_launcher=original_launcher[:original_launcher.index('HELPER=')]+original_launcher[original_launcher.index('CHROMIUM_APPS=('):]
    assert 'wta_webview' not in main_launcher and 'osascript' not in main_launcher and '--app="$WTA_URL"' in main_launcher
    native_launcher=original_launcher[:original_launcher.index('if /usr/bin/osascript')]
    native_launcher += 'printf "%s\\n" "原生窗口无法启动，请使用主要浏览器入口。" >&2\nexit 1\n'
    entries={};main_root='雅思学习册.app/Contents/';native_root='雅思学习册-原生受限备用.app/Contents/'
    base_plist=plistlib.loads(raw[prefix+'Info.plist']);base_plist.pop('NSAppTransportSecurity',None)
    for root,identifier,name,launcher in [(main_root,'com.webtoapp.ieltsstudy','雅思学习册',main_launcher),(native_root,'com.webtoapp.ieltsstudy.native','雅思学习册-原生受限备用',native_launcher)]:
        plist={**base_plist,'CFBundleIdentifier':identifier,'CFBundleName':name,'CFBundleDisplayName':name,'CFBundleVersion':'1.0.0','CFBundleShortVersionString':'1.0.0','LSMinimumSystemVersion':'11.0','NSMicrophoneUsageDescription':'仅用于你主动开始的雅思口语录音练习；音频须由你另行下载。'}
        entries[root+'Info.plist']=plistlib.dumps(plist,sort_keys=True)
        entries[root+'MacOS/launcher']=launcher.encode('utf8')
        entries[root+'Resources/AppIcon.icns']=raw[prefix+'Resources/AppIcon.icns']
    entries[native_root+'MacOS/wta_webview']=helper
    entries['在浏览器打开.webloc']=plistlib.dumps({'URL':URL})
    entries['使用说明.txt']=README.encode('utf8');entries['LICENSE-WebToApp.txt']=(upstream/'LICENSE').read_bytes()
    bash=Path('C:/Program Files/Git/bin/bash.exe')
    if bash.exists():
        with tempfile.TemporaryDirectory(prefix='ielts-shell-check-') as scratch:
            for name,contents in [('main.sh',main_launcher),('native.sh',native_launcher)]:
                f=Path(scratch)/name;f.write_text(contents,encoding='utf8',newline='');subprocess.run([str(bash),'-n',str(f)],check=True,capture_output=True)
    target=out/'macos.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries.items():
            item=zipfile.ZipInfo(name,date_time=(2026,9,21,0,0,0));item.create_system=3;item.compress_type=zipfile.ZIP_DEFLATED;item.external_attr=(0o100755 if '/MacOS/' in name else 0o100644)<<16;z.writestr(item,data)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert z.read(native_root+'MacOS/wta_webview')==helper
        assert all((z.getinfo(root+'MacOS/launcher').external_attr>>16)&0o111 for root in [main_root,native_root])
        assert plistlib.loads(z.read('在浏览器打开.webloc'))['URL']==URL
        assert len([n for n in z.namelist() if n.endswith('Info.plist')])==2
    report={'url':URL,'upstream':'https://github.com/shiaho777/WebToApp','upstream_commit':PIN,'upstream_builder_sha256':sha(source_path.read_bytes()),'artifact_kind':'macOS browser-app-mode entry plus limited native WKWebView alternative','default_bundle_id':'com.webtoapp.ieltsstudy','native_bundle_id':'com.webtoapp.ieltsstudy.native','minimum_macos':'11.0','helper_sha256':sha(helper),'helper_architectures':['x86_64','arm64'],'helper_bytes_preserved':True,'shell_syntax_checked':bash.exists(),'zip_and_plist_checks':True,'native_known_gaps':['file chooser','JS confirm/prompt','downloads and Blob export','external link handling'],'physical_device_tested':False,'developer_id_signed_or_notarized':False,'files':[{'name':'macos.zip','bytes':target.stat().st_size,'sha256':sha(target.read_bytes())}]}
    (out/'macos-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
