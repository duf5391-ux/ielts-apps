import UIKit
import WebKit
import AVFoundation

@main final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication, didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let window = UIWindow(frame: UIScreen.main.bounds)
        window.rootViewController = StudyController()
        self.window = window; window.makeKeyAndVisible()
        return true
    }
}

final class StudyController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
    private var web: WKWebView!
    private var server: LocalServer!
    private var downloaded = [ObjectIdentifier: URL]()
    private var smokeStarted = false
    private let smoke = ProcessInfo.processInfo.arguments.contains("--offline-smoke-test")

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.98, green: 0.98, blue: 0.96, alpha: 1)
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self; web.uiDelegate = self
        web.allowsBackForwardNavigationGestures = true
        web.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(web)
        NSLayoutConstraint.activate([
            web.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor),
            web.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor),
            web.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            web.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor)
        ])
        server = LocalServer(root: Bundle.main.resourceURL!.appendingPathComponent("site"))
        if smoke {
            // CI proves startup and learning reads with all non-loopback network blocked.
            let rules = """
            [{"trigger":{"url-filter":"^https?://","unless-domain":["127.0.0.1"]},"action":{"type":"block"}}]
            """
            WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "offline-test", encodedContentRuleList: rules) { [weak self] list, error in
                guard let self = self else { return }
                guard let list = list else { self.writeSmoke(["error": String(describing: error)]); return }
                config.userContentController.add(list); self.start()
            }
        } else { start() }
    }

    private func start() {
        server.start { [weak self] error in
            guard let self = self else { return }
            if let error = error { self.alert("无法打开学习册", message: "本机内容服务启动失败，请关闭 App 后重试。\n\(error.localizedDescription)"); return }
            self.web.load(URLRequest(url: URL(string: HTTPFile.origin + "/index.html")!))
        }
    }

    private func isLocal(_ url: URL?) -> Bool {
        url?.scheme == "http" && url?.host == "127.0.0.1" && url?.port == 18761
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { decisionHandler(.cancel); return }
        if action.shouldPerformDownload && (isLocal(webView.url)) && (isLocal(url) || ["blob", "data"].contains(url.scheme ?? "")) {
            decisionHandler(.download); return
        }
        if isLocal(url) { decisionHandler(.allow); return }
        if action.targetFrame?.isMainFrame == false { decisionHandler(.cancel); return }
        decisionHandler(.cancel)
        if ["https", "http"].contains(url.scheme ?? ""), !smoke { UIApplication.shared.open(url) }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if isLocal(action.request.url) { webView.load(action.request) }
        else if let url = action.request.url, url.scheme == "https", !smoke { UIApplication.shared.open(url) }
        return nil
    }

    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        let permitted = origin.protocol == "http" && origin.host == "127.0.0.1" && origin.port == 18761 && type == .microphone
        decisionHandler(permitted ? .prompt : .deny)
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let sheet = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        sheet.addAction(UIAlertAction(title: "好", style: .default) { _ in completionHandler() }); present(sheet, animated: true)
    }
    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
        let sheet = UIAlertController(title: nil, message: message, preferredStyle: .alert)
        sheet.addAction(UIAlertAction(title: "取消", style: .cancel) { _ in completionHandler(false) })
        sheet.addAction(UIAlertAction(title: "确定", style: .default) { _ in completionHandler(true) }); present(sheet, animated: true)
    }
    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let sheet = UIAlertController(title: nil, message: prompt, preferredStyle: .alert)
        sheet.addTextField { $0.text = defaultText }
        sheet.addAction(UIAlertAction(title: "取消", style: .cancel) { _ in completionHandler(nil) })
        sheet.addAction(UIAlertAction(title: "确定", style: .default) { _ in completionHandler(sheet.textFields?.first?.text) }); present(sheet, animated: true)
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("Exports")
        do {
            try FileManager.default.createDirectory(at: documents, withIntermediateDirectories: true)
            let name = URL(fileURLWithPath: suggestedFilename).lastPathComponent
            let file = documents.appendingPathComponent(UUID().uuidString.prefix(8) + "-" + (name.isEmpty ? "备份" : name))
            downloaded[ObjectIdentifier(download)] = file; completionHandler(file)
        } catch { completionHandler(nil); alert("保存失败", message: error.localizedDescription) }
    }
    func downloadDidFinish(_ download: WKDownload) {
        guard let file = downloaded.removeValue(forKey: ObjectIdentifier(download)) else { return }
        if smoke { return }
        let sheet = UIActivityViewController(activityItems: [file], applicationActivities: nil)
        sheet.popoverPresentationController?.sourceView = view
        sheet.popoverPresentationController?.sourceRect = CGRect(x: view.bounds.midX, y: view.bounds.midY, width: 1, height: 1)
        present(sheet, animated: true)
    }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        downloaded.removeValue(forKey: ObjectIdentifier(download))
        alert("下载失败", message: error.localizedDescription)
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard smoke, !smokeStarted, isLocal(webView.url) else { return }
        smokeStarted = true
        let script = (try? String(contentsOf: Bundle.main.url(forResource: "smoke", withExtension: "js")!, encoding: .utf8)) ?? "return {error:'no smoke script'};"
        webView.callAsyncJavaScript(script, arguments: [:], in: nil, in: .page) { [weak self] result in
            switch result {
            case .success(let value): self?.writeSmoke(value as? [String: Any] ?? ["error":"invalid report"])
            case .failure(let error): self?.writeSmoke(["error": error.localizedDescription])
            }
        }
    }

    private func writeSmoke(_ report: [String: Any]) {
        let file = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("offline-smoke.json")
        if let data = try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]) { try? data.write(to: file, options: .atomic) }
    }
    private func alert(_ title: String, message: String) {
        let sheet = UIAlertController(title: title, message: message, preferredStyle: .alert)
        sheet.addAction(UIAlertAction(title: "好", style: .default)); present(sheet, animated: true)
    }
}
