# macOS入口

`build_macos.py` 复用固定版本 `shiaho777/WebToApp` 的原始macOS组装方法、图标与二进制；从AST加载这一方法和必要助手，避免为了离线打包导入无关HTTP服务。需要Python与Pillow。

```powershell
python MacOS/build_macos.py --upstream ../tools/webtoapp --config config/app.json --output ../app-delivery/artifacts
```

默认「雅思学习册.app」直接使用上游已有Chromium app-mode／默认浏览器分支。原生WKWebView另存受限备用，保留universal helper全部字节，补最低系统和麦克风用途说明，移除无必要的HTTP任意加载许可。默认身份`com.webtoapp.ieltsstudy`，原生备用身份`com.webtoapp.ieltsstudy.native`，记录分别保存在对应浏览器或WebView。

原生模板没有WKUIDelegate文件选择、确认框与完整下载桥，不能当作功能完整入口。包中说明和webloc直接网页入口明确这一点。未Apple Developer ID签名/公证，未Mac实机安装或验证Gatekeeper、权限、音频、导入导出和重启恢复。构建检查只覆盖源版本、二进制架构/哈希、plist、ZIP执行位及可用环境下的shell语法。

整个过程不修改上游源码、不读取用户学习记录、不创建新签名、不安装服务。
