import Foundation

// Immutable bundled content only. No access to Documents, recordings or records.
struct HTTPFile {
    let status: Int
    let headers: [String: String]
    let file: URL?
    let offset: UInt64
    let count: UInt64
    let head: Bool

    static let authority = "127.0.0.1:18761"
    static let origin = "http://" + authority

    static func response(_ request: String, root: URL) -> HTTPFile {
        func fail(_ status: Int, _ headers: [String: String] = [:]) -> HTTPFile {
            HTTPFile(status: status, headers: headers, file: nil, offset: 0, count: 0, head: false)
        }
        let lines = request.components(separatedBy: "\r\n")
        let parts = (lines.first ?? "").split(separator: " ")
        guard parts.count == 3 else { return fail(400) }
        let method = String(parts[0])
        guard method == "GET" || method == "HEAD" else { return fail(405, ["Allow": "GET, HEAD"]) }
        var headers = [String: String]()
        for line in lines.dropFirst() where !line.isEmpty {
            guard let colon = line.firstIndex(of: ":") else { return fail(400) }
            let key = line[..<colon].lowercased()
            guard headers[key] == nil else { return fail(400) }
            headers[key] = line[line.index(after: colon)...].trimmingCharacters(in: .whitespaces)
        }
        guard headers["host"] == authority else { return fail(403) }
        if let origin = headers["origin"], origin != Self.origin { return fail(403) }
        if headers["sec-fetch-site"] == "cross-site" { return fail(403) }
        let target = String(parts[1]).components(separatedBy: "?")[0]
        guard target.hasPrefix("/"), !target.hasPrefix("//"),
              let decoded = target.removingPercentEncoding, !decoded.contains("\0"),
              !decoded.contains("\\"), !decoded.split(separator: "/").contains("..") else { return fail(400) }
        let cleanRoot = root.resolvingSymlinksInPath().standardizedFileURL
        let path = decoded == "/" ? "index.html" : String(decoded.dropFirst())
        let file = cleanRoot.appendingPathComponent(path).resolvingSymlinksInPath().standardizedFileURL
        guard file.path.hasPrefix(cleanRoot.path + "/") else { return fail(403) }
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: file.path),
              attrs[.type] as? FileAttributeType == .typeRegular,
              let number = attrs[.size] as? NSNumber else { return fail(404) }
        let size = number.uint64Value
        var offset: UInt64 = 0, count = size, status = 200
        var result = ["Content-Type": mime(file.pathExtension), "Accept-Ranges": "bytes",
                      "Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"]
        if let range = headers["range"], method == "GET" {
            let invalid = fail(416, ["Content-Range": "bytes */\(size)"])
            guard range.hasPrefix("bytes="), !range.contains(","), size > 0 else { return invalid }
            let bounds = range.dropFirst(6).split(separator: "-", omittingEmptySubsequences: false)
            guard bounds.count == 2 else { return invalid }
            if bounds[0].isEmpty {
                guard let suffix = UInt64(bounds[1]), suffix > 0 else { return invalid }
                count = min(suffix, size); offset = size - count
            } else {
                guard let start = UInt64(bounds[0]), start < size else { return invalid }
                let end: UInt64
                if bounds[1].isEmpty { end = size - 1 }
                else { guard let value = UInt64(bounds[1]), value >= start else { return invalid }; end = min(value, size - 1) }
                offset = start; count = end - start + 1
            }
            status = 206
            result["Content-Range"] = "bytes \(offset)-\(offset + count - 1)/\(size)"
        }
        return HTTPFile(status: status, headers: result, file: file, offset: offset, count: count, head: method == "HEAD")
    }

    var headerData: Data {
        let reasons = [200:"OK",206:"Partial Content",400:"Bad Request",403:"Forbidden",404:"Not Found",405:"Method Not Allowed",416:"Range Not Satisfiable"]
        var text = "HTTP/1.1 \(status) \(reasons[status] ?? "Error")\r\nConnection: close\r\nContent-Length: \(count)\r\n"
        for (key, value) in headers { text += "\(key): \(value)\r\n" }
        return Data((text + "\r\n").utf8)
    }

    static func mime(_ ext: String) -> String {
        let types = ["html":"text/html; charset=utf-8", "js":"text/javascript; charset=utf-8", "css":"text/css; charset=utf-8",
         "json":"application/json", "webmanifest":"application/manifest+json", "svg":"image/svg+xml",
         "png":"image/png", "jpg":"image/jpeg", "jpeg":"image/jpeg", "webp":"image/webp",
         "mp3":"audio/mpeg", "m4a":"audio/mp4", "mp4":"video/mp4", "ogg":"audio/ogg", "wav":"audio/wav",
         "pdf":"application/pdf", "woff":"font/woff", "woff2":"font/woff2", "txt":"text/plain; charset=utf-8"]
        return types[ext.lowercased()] ?? "application/octet-stream"
    }
}
