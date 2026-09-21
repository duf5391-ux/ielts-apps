"""Build the IELTS URL APK from the pinned shiaho777/WebToApp template.

Only uses an existing Android SDK and an existing, persistent PKCS12 identity.
It never installs SDK packages, accepts licenses, creates app keys, or emits a
ZIP fallback. The upstream checkout is disposable; no source file is edited.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

UPSTREAM_COMMIT = "3704633018bfef5fbf2783e3b59870eac8bc109c"
APP_ID = "ieltsstudy"
PACKAGE = "app.ielts.ieltsstudy"
APP_NAME = "雅思学习册"
URL = "https://duf5391-ux.github.io/ielts-learning/"
THEME = "#356c57"
VERSION_CODE = 1
VERSION_NAME = "1.0.0"


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, *, env=None, data=None):
    result = subprocess.run(command, input=data, capture_output=True, env=env)
    if result.returncode:
        # Never include command arguments: an upstream command may contain a
        # password. Tool stderr is reported by the outer, redacting wrapper.
        error = BuildError(f"{Path(command[0]).name} failed (exit {result.returncode})")
        error.tool_stderr = result.stderr.decode("utf-8", errors="replace")
        raise error
    return result.stdout.decode("utf-8", errors="replace")


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise BuildError("Pinned template no longer matches the adaptation contract")
    return source.replace(old, new, 1)


def adapt_template(module):
    """Small IELTS policy/theme adapter; retain upstream storage/media bridges."""
    java = module.ACTIVITY_JAVA
    java = replace_once(java, "webView = new WebView(this);", """webView = new WebView(this);
        webView.setBackgroundColor(android.graphics.Color.parseColor("#356c57"));
        getWindow().setStatusBarColor(android.graphics.Color.parseColor("#356c57"));
        getWindow().setNavigationBarColor(android.graphics.Color.parseColor("#356c57"));""")
    java = replace_once(java,
        "s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);",
        "s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);")
    java = replace_once(java, "s.setGeolocationEnabled(true);", "s.setGeolocationEnabled(false);")
    java = replace_once(java,
        "s.setUserAgentString(config.desktopMode ? DESKTOP_USER_AGENT : sanitizeUserAgent(ua));",
        "s.setUserAgentString(ua);")
    java = replace_once(java, "byte[] data = input.readAllBytes();", """java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int bytesRead;
            while ((bytesRead = input.read(chunk)) != -1) buffer.write(chunk, 0, bytesRead);
            byte[] data = buffer.toByteArray();""")
    java = replace_once(java, "if (config == null || !config.immersiveFullscreen) return;", """if (config == null || !config.immersiveFullscreen) {
            // targetSdk 35+ enforces edge-to-edge even in ordinary windowed
            // mode. Keep study controls above system bars and the keyboard.
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                getWindow().setDecorFitsSystemWindows(false);
                webView.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
                    @Override public WindowInsets onApplyWindowInsets(View view, WindowInsets insets) {
                        android.graphics.Insets safe = insets.getInsets(
                            WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                        view.setPadding(safe.left, safe.top, safe.right, safe.bottom);
                        return WindowInsets.CONSUMED;
                    }
                });
                webView.requestApplyInsets();
            }
            return;
        }""")
    java = replace_once(java,
        "handleGeolocationPermission(origin, callback);",
        "callback.invoke(origin, false, false);")
    java = replace_once(java, "private boolean handleNavigation(String url) {", """private boolean isStudyOrigin(Uri uri) {
        return uri != null && "https".equalsIgnoreCase(uri.getScheme())
            && "duf5391-ux.github.io".equalsIgnoreCase(uri.getHost())
            && (uri.getPort() == -1 || uri.getPort() == 443);
    }

    private boolean handleNavigation(String url) {""")
    java = replace_once(java,
        "String trimmed = url.trim();",
        """String trimmed = url.trim();
        Uri destination = Uri.parse(trimmed);
        if ("http".equalsIgnoreCase(destination.getScheme()) || "https".equalsIgnoreCase(destination.getScheme())) {
            String path = destination.getPath();
            if (!isStudyOrigin(destination) || path == null || !path.startsWith("/ielts-learning/")) {
                return openExternal(trimmed);
            }
        }""")
    for protocol in ("about:", "javascript:", "data:"):
        java = replace_once(java, f'            lower.startsWith("{protocol}") ||\n', "")
    java = replace_once(java,
        '        if (lower.startsWith("intent://")) {',
        '''        if (lower.startsWith("about:") || lower.startsWith("javascript:") || lower.startsWith("data:")) return true;
        if (lower.startsWith("intent://")) {''')
    java = replace_once(java, "if (request == null) return;", """if (request == null) return;
        // Android permission alone is insufficient: bind media to our origin
        // and grant only the audio capability requested by the study recorder.
        if (!isStudyOrigin(request.getOrigin()) || request.getResources().length != 1
                || !PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(request.getResources()[0])) {
            request.deny();
            return;
        }""")
    java = replace_once(java,
        "webView.loadUrl(fallback);",
        "if (!handleNavigation(fallback)) webView.loadUrl(fallback);")
    manifest = module.MANIFEST_XML
    for permission in ("ACCESS_COARSE_LOCATION", "ACCESS_FINE_LOCATION", "CAMERA"):
        manifest = replace_once(manifest,
            f'    <uses-permission android:name="android.permission.{permission}"/>\n', "")
    manifest = replace_once(manifest, 'android:usesCleartextTraffic="true"',
        'android:usesCleartextTraffic="false" android:allowBackup="false"')
    manifest = replace_once(manifest, 'android:minSdkVersion="21"', 'android:minSdkVersion="23"')
    module.ACTIVITY_JAVA = java
    module.MANIFEST_XML = manifest
    return {
        "java_sha256": hashlib.sha256(java.encode()).hexdigest(),
        "manifest_template_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "changes": ["IELTS theme", "native WebView user agent", "HTTPS only",
                    "external main-frame links open in browser", "origin-bound microphone only",
                    "no camera/location permissions", "Android system backup disabled",
                    "Android 6+ compatible config reader", "system bar and keyboard insets"],
    }


def validate_keys(key_dir: Path):
    keystore = key_dir / f"{APP_ID}.keystore"
    metadata = key_dir / f"{APP_ID}.json"
    if not keystore.is_file() or not metadata.is_file():
        raise BuildError("Persistent signing files missing; refusing to generate a replacement identity")
    try:
        meta = json.loads(metadata.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError):
        raise BuildError("Signing metadata is not valid UTF-8 JSON") from None
    if not isinstance(meta, dict) or not all(isinstance(meta.get(k), str) and meta[k] for k in ("alias", "password")):
        raise BuildError("Signing metadata requires nonempty alias and password strings")
    if len(meta["password"]) < 12:
        raise BuildError("Signing metadata password is unexpectedly short")
    return keystore, metadata, meta


def build(args):
    upstream = args.upstream.resolve()
    out = args.output.resolve()
    key_dir = args.key_dir.resolve()
    icon = args.icon.resolve()
    if key_dir == out or key_dir.is_relative_to(out) or out.is_relative_to(key_dir):
        raise BuildError("Private signing directory and public output directory must be separate")
    if run(["git", "-C", str(upstream), "rev-parse", "HEAD"]).strip() != UPSTREAM_COMMIT:
        raise BuildError("Upstream checkout is not the pinned commit")
    if run(["git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=no"]).strip():
        raise BuildError("Upstream tracked files are modified")
    if not icon.is_file() or not icon.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
        raise BuildError("A PNG application icon is required")
    sdk_raw = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk_raw:
        raise BuildError("Existing Android SDK is required; automatic installation is disabled")
    sdk = Path(sdk_raw).resolve()
    bt = sdk / "build-tools" / "36.0.0"
    android_jar = sdk / "platforms" / "android-36" / "android.jar"
    for name in ("aapt2", "d8", "apksigner", "zipalign"):
        if not (bt / name).is_file():
            raise BuildError(f"Preinstalled Android build-tools 36.0.0 lacks {name}")
    if not android_jar.is_file():
        raise BuildError("Preinstalled Android platform 36 is required")
    for name in ("java", "javac", "keytool", "openssl"):
        if not shutil.which(name):
            raise BuildError(f"Existing {name} is required")
    keystore, metadata, meta = validate_keys(key_dir)
    initial_keys = (sha(keystore), sha(metadata))
    env = dict(os.environ, IELTS_KEY_PASSWORD=meta["password"])
    cert_pem = run(["keytool", "-exportcert", "-rfc", "-keystore", str(keystore),
                    "-storetype", "PKCS12", "-storepass:env", "IELTS_KEY_PASSWORD",
                    "-alias", meta["alias"]], env=env)
    cert_sha = run(["openssl", "x509", "-noout", "-fingerprint", "-sha256"],
                   data=cert_pem.encode()).strip().split("=", 1)[-1].replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", cert_sha):
        raise BuildError("Could not determine the signing certificate SHA-256")
    if meta.get("certificate_sha256") and meta["certificate_sha256"].replace(":", "").lower() != cert_sha:
        raise BuildError("Signing identity differs from its saved certificate fingerprint")
    os.environ["ANDROID_KEYSTORE_DIR"] = str(key_dir)
    sys.path.insert(0, str(upstream))
    module = importlib.import_module("server.engine.apk_builder")
    adaptations = adapt_template(module)

    class IeltsBuilder(module.ApkBuilder):
        TEMPLATE_REVISION = "2026-09-21-ielts-https-audio-1"

        def _find_tools(self, name):
            return [str(bt / name)] if (bt / name).is_file() else []

        def _find_jar(self):
            return str(android_jar)

        def _ensure_app_keystore(self, app_id):
            if app_id != APP_ID:
                raise BuildError("Unexpected signing app identity")
            return keystore, meta["password"], meta["alias"]

        def _patch_template_apk(self, template_apk, output, url, name, pkg,
                                icon_png, version_code, version_name, feature_options, app_id=None):
            # Retain the upstream binary manifest/asset patcher and aligner;
            # use Android's official signer, never masqueraded signing metadata.
            self._ensure_app_keystore(app_id)
            with tempfile.TemporaryDirectory() as directory:
                patched = Path(directory) / "patched.apk"
                self._patch_apk_entries(template_apk, patched,
                    manifest=self._patched_manifest_xml(template_apk, pkg, version_code, version_name, name),
                    replacements={"assets/webtoapp_config.json": self._config_json(url, feature_options).encode(),
                                  "res/mipmap/ic_launcher.png": icon_png})
                with zipfile.ZipFile(patched, "a", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("assets/licenses/WebToApp-MIT.txt", (upstream / "LICENSE").read_bytes())
                output.parent.mkdir(parents=True, exist_ok=True)
                self._align_apk(patched, output)
                run([str(bt / "apksigner"), "sign", "--ks", str(keystore), "--ks-key-alias", meta["alias"],
                     "--ks-pass", "env:IELTS_KEY_PASSWORD", "--key-pass", "env:IELTS_KEY_PASSWORD",
                     "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
                     "--v3-signing-enabled", "true", "--v4-signing-enabled", "false", str(output)], env=env)

    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise BuildError("Output directory must be empty to avoid publishing stale artifacts")
    builder = IeltsBuilder()
    apk = out / "android.apk"
    # Directly use the template methods, so upstream's catch-and-print wrapper
    # cannot leak process arguments on failure or fall back to a web ZIP.
    template = builder._ensure_template_apk(icon.read_bytes())
    if not template or not template.is_file():
        raise BuildError("Template APK compilation failed")
    builder._patch_template_apk(template, apk, URL, APP_NAME, PACKAGE, icon.read_bytes(),
                                VERSION_CODE, VERSION_NAME, {}, APP_ID)
    if not builder._validate_built_apk(apk):
        raise BuildError("APK ZIP alignment validation failed")
    verify = run([str(bt / "apksigner"), "verify", "--verbose", "--print-certs", str(apk)])
    signed_fingerprints = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)", verify)
    if signed_fingerprints != [cert_sha]:
        raise BuildError("APK signer differs from the persistent identity")
    run([str(bt / "zipalign"), "-c", "4", str(apk)])
    badging = run([str(bt / "aapt2"), "dump", "badging", str(apk)])
    for expected in (f"name='{PACKAGE}'", f"versionCode='{VERSION_CODE}'", f"versionName='{VERSION_NAME}'"):
        if expected not in badging.splitlines()[0]:
            raise BuildError("Compiled APK package/version identity mismatch")
    if f"application-label:'{APP_NAME}'" not in badging:
        raise BuildError("Compiled APK application label mismatch")
    if "android.permission.CAMERA" in badging or "android.permission.ACCESS_FINE_LOCATION" in badging:
        raise BuildError("APK contains an unneeded camera/location permission")
    with zipfile.ZipFile(apk) as zf:
        config = json.loads(zf.read("assets/webtoapp_config.json"))
        if config.get("url") != URL or config.get("desktop_mode") or config.get("immersive_fullscreen"):
            raise BuildError("APK embedded URL or mobile-mode configuration mismatch")
        if zf.read("res/mipmap/ic_launcher.png") != icon.read_bytes():
            raise BuildError("APK icon differs from the unified application icon")
        if zf.read("assets/licenses/WebToApp-MIT.txt") != (upstream / "LICENSE").read_bytes():
            raise BuildError("Upstream license notice is missing or changed")
        if "classes.dex" not in zf.namelist() or "AndroidManifest.xml" not in zf.namelist():
            raise BuildError("Output is not a compiled Android APK")
    if (sha(keystore), sha(metadata)) != initial_keys:
        raise BuildError("Persistent signing files changed during the build")
    report = {
        "app_id": APP_ID, "package": PACKAGE, "name": APP_NAME, "url": URL,
        "theme_color": THEME, "version_code": VERSION_CODE, "version_name": VERSION_NAME,
        "upstream": "https://github.com/shiaho777/WebToApp", "upstream_commit": UPSTREAM_COMMIT,
        "build_tools": "36.0.0", "compile_sdk": 36, "target_sdk": 36, "min_sdk": 23,
        "sdk_license_acceptance_executed": False, "apk_sha256": sha(apk), "apk_bytes": apk.stat().st_size,
        "icon_sha256": sha(icon), "certificate_sha256": cert_sha,
        "signature_verification": "passed", "zip_alignment_verification": "passed",
        "artifact_kind": "signed Android APK (online URL shell)",
        "physical_device_tested": False, "personal_record_cloud_sync": False,
        "runtime_adapter": adaptations,
        "source_files": {p: sha(upstream / p) for p in (
            "server/engine/apk_builder.py", "server/engine/apk_v2_signer.py", "server/config.py")},
        "builder_sha256": sha(Path(__file__)),
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "apksigner-verify.txt").write_text(verify, encoding="utf-8")
    (out / "apk-badging.txt").write_text(badging, encoding="utf-8")
    print(json.dumps({"artifact": "android.apk", "apk_sha256": report["apk_sha256"],
                      "certificate_sha256": cert_sha, "bytes": report["apk_bytes"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--icon", type=Path, required=True)
    parser.add_argument("--key-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args)
    except Exception as error:
        # No traceback/process args on a signing failure. Report only known
        # error text; stderr can include arbitrary tool arguments, so omit it.
        message = str(error) if isinstance(error, BuildError) else type(error).__name__
        print(f"Android build failed: {message}", file=sys.stderr)
        diagnostic = getattr(error, "stderr", None) or getattr(error, "tool_stderr", "")
        if isinstance(diagnostic, bytes):
            diagnostic = diagnostic.decode("utf-8", errors="replace")
        if diagnostic:
            try:
                secret_meta = json.loads((args.key_dir / f"{APP_ID}.json").read_text(encoding="utf-8-sig"))
                import base64
                for value in (secret_meta.get("password"),):
                    if value:
                        diagnostic = diagnostic.replace(value, "[redacted]")
                        diagnostic = diagnostic.replace(base64.b64encode(value.encode()).decode(), "[redacted]")
                print(diagnostic[:4000], file=sys.stderr)
            except Exception:
                pass  # Do not print an unredacted tool diagnostic.
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
