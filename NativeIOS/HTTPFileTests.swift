import Foundation

@main struct Tests {
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        try Data("0123456789".utf8).write(to: root.appendingPathComponent("index.html"))
        try Data("中文".utf8).write(to: root.appendingPathComponent("中文.txt"))
        func response(_ path: String = "/", method: String = "GET", headers: String = "") -> HTTPFile {
            HTTPFile.response("\(method) \(path) HTTP/1.1\r\nHost: \(HTTPFile.authority)\r\n\(headers)\r\n", root: root)
        }
        assert(response().status == 200 && response().count == 10)
        assert(response(method: "HEAD").head)
        assert(response(method: "POST").status == 405)
        assert(response("/missing").status == 404)
        assert(response("/%E4%B8%AD%E6%96%87.txt").status == 200)
        assert(response("/%2e%2e/secret").status == 400)
        assert(response("/../secret").status == 400)
        assert(response("/%00.txt").status == 400)
        assert(response("//example.com/").status == 400)
        assert(response(headers: "Origin: https://example.com\r\n").status == 403)
        assert(response(headers: "Sec-Fetch-Site: cross-site\r\n").status == 403)
        assert(response(headers: "Host: example.com\r\n").status == 400)
        let first = response(headers: "Range: bytes=2-5\r\n")
        assert(first.status == 206 && first.offset == 2 && first.count == 4)
        let tail = response(headers: "Range: bytes=-3\r\n")
        assert(tail.status == 206 && tail.offset == 7 && tail.count == 3)
        assert(response(headers: "Range: bytes=8-\r\n").count == 2)
        assert(response(headers: "Range: bytes=9-99\r\n").count == 1)
        for range in ["bytes=10-", "bytes=2-1", "bytes=-0", "bytes=a-b", "bytes=0-1,4-5"] {
            assert(response(headers: "Range: \(range)\r\n").status == 416)
        }
        print("HTTPFile: 21 path, origin, method and audio-range assertions passed")
    }
}
