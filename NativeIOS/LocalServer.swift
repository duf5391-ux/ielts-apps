import Foundation
import Network

final class LocalServer {
    private let queue = DispatchQueue(label: "app.ielts.bundle-server")
    private var listener: NWListener?
    private let root: URL
    init(root: URL) { self.root = root }

    func start(ready: @escaping (Error?) -> Void) {
        guard listener == nil else { ready(nil); return }
        do {
            let parameters = NWParameters.tcp
            parameters.requiredLocalEndpoint = .hostPort(host: "127.0.0.1", port: 18761)
            parameters.allowLocalEndpointReuse = true
            let next = try NWListener(using: parameters)
            var notified = false
            next.stateUpdateHandler = { state in
                switch state {
                case .ready:
                    if !notified { notified = true; DispatchQueue.main.async { ready(nil) } }
                case .failed(let error):
                    if !notified { notified = true; DispatchQueue.main.async { ready(error) } }
                default: break
                }
            }
            next.newConnectionHandler = { [weak self] connection in
                guard let self = self else { connection.cancel(); return }
                connection.start(queue: self.queue)
                self.receive(connection, buffer: Data())
                self.queue.asyncAfter(deadline: .now() + 30) { connection.cancel() }
            }
            listener = next
            next.start(queue: queue)
        } catch { ready(error) }
    }

    private func receive(_ connection: NWConnection, buffer: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 8192) { [weak self] chunk, _, complete, error in
            guard let self = self, error == nil else { connection.cancel(); return }
            var data = buffer; data.append(chunk ?? Data())
            guard data.count <= 32768 else { connection.cancel(); return }
            if let end = data.range(of: Data("\r\n\r\n".utf8)),
               let text = String(data: data[..<end.upperBound], encoding: .utf8) {
                self.send(HTTPFile.response(text, root: self.root), connection)
            } else if complete { connection.cancel() }
            else { self.receive(connection, buffer: data) }
        }
    }

    private func send(_ response: HTTPFile, _ connection: NWConnection) {
        let file = response.file.flatMap { try? FileHandle(forReadingFrom: $0) }
        if let file = file { try? file.seek(toOffset: response.offset) }
        connection.send(content: response.headerData, completion: .contentProcessed { [weak self] error in
            guard error == nil, !response.head, response.count > 0, let file = file, let self = self else {
                try? file?.close(); connection.cancel(); return
            }
            self.stream(file, remaining: response.count, connection: connection)
        })
    }

    private func stream(_ file: FileHandle, remaining: UInt64, connection: NWConnection) {
        guard remaining > 0, let data = try? file.read(upToCount: Int(min(remaining, 65536))), !data.isEmpty else {
            try? file.close(); connection.cancel(); return
        }
        connection.send(content: data, completion: .contentProcessed { [weak self] error in
            if error != nil { try? file.close(); connection.cancel() }
            else { self?.stream(file, remaining: remaining - UInt64(data.count), connection: connection) }
        })
    }
}
