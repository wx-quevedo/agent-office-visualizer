import Foundation

// Chat vivo (Prompt 46): estados de los mensajes, burbuja de la respuesta en curso,
// lectura del canal SSE y cuándo usar la ruta liviana. Sin SwiftUI ni red:
// se prueba en ChatVivoTests.

/// Lee un flujo Server-Sent Events línea por línea. Cada evento `chat` trae el JSON
/// de `/chat/en-vivo` en una sola línea `data:`; se entrega apenas el JSON está
/// completo (sin esperar la línea en blanco, que `URLSession.lines` puede omitir).
struct LectorSSE {
    private var evento = "message"
    private var datos = ""

    /// Una línea del flujo; devuelve el `ChatEnVivo` cuando un evento `chat` está completo.
    mutating func linea(_ l: String) -> ChatEnVivo? {
        if l.isEmpty {
            defer { reiniciar() }
            return entregar()
        }
        if l.hasPrefix(":") { return nil } // comentario (": pulso")
        let (campo, valor) = Self.partir(l)
        switch campo {
        case "event":
            // Un evento nuevo cierra el anterior si quedó sin línea en blanco.
            let previo = entregar()
            reiniciar()
            evento = valor
            return previo
        case "data":
            datos += datos.isEmpty ? valor : "\n" + valor
            if let listo = entregar() {
                reiniciar()
                return listo
            }
            return nil
        default:
            return nil // retry, id
        }
    }

    private func entregar() -> ChatEnVivo? {
        guard evento == "chat", !datos.isEmpty else { return nil }
        return try? JSONDecoder().decode(ChatEnVivo.self, from: Data(datos.utf8))
    }

    private mutating func reiniciar() {
        evento = "message"
        datos = ""
    }

    private static func partir(_ l: String) -> (String, String) {
        guard let i = l.firstIndex(of: ":") else { return (l, "") }
        var v = l[l.index(after: i)...]
        if v.hasPrefix(" ") { v = v.dropFirst() }
        return (String(l[..<i]), String(v))
    }
}

/// Lo que se muestra al final del chat mientras el orquestador trabaja.
enum BurbujaVivo: Equatable {
    case ninguna
    case puntos
    case texto(String)
}

enum LogicaChatVivo {
    /// Marca discreta debajo de un mensaje de Washington: "Enviado" y luego "Leído".
    static func marca(_ m: MensajeChat) -> String? {
        guard m.autor == "washington" else { return nil }
        switch m.estado {
        case "leido", "respondiendo": return "Leído"
        case "enviado": return m.leido == nil ? "Enviado" : "Leído"
        default: return m.leido != nil ? "Leído" : nil
        }
    }

    /// Tres puntos mientras trabaja sin texto; el texto parcial cuando ya hay.
    static func burbuja(_ v: EnVivo?) -> BurbujaVivo {
        guard let v, v.estado == "respondiendo" else { return .ninguna }
        let t = (v.parcial ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? .puntos : .texto(v.parcial ?? "")
    }

    /// Une los últimos mensajes de una lectura liviana: reemplaza por id (el estado y
    /// la hora de leído cambian) y agrega los nuevos al final, en orden.
    static func unir(_ mensajes: [MensajeChat], _ recientes: [MensajeChat]) -> [MensajeChat] {
        var salida = mensajes
        var indice = Dictionary(uniqueKeysWithValues: salida.enumerated().map { ($1.id, $0) })
        for r in recientes {
            if let i = indice[r.id] {
                salida[i] = r
            } else {
                indice[r.id] = salida.count
                salida.append(r)
            }
        }
        return salida
    }

    /// La ruta liviana solo hace falta mientras hay respuesta en curso o un mensaje
    /// de Washington sin leer.
    static func debeSondear(_ v: EnVivo?, _ mensajes: [MensajeChat]) -> Bool {
        if let v, v.estado != "libre" { return true }
        return mensajes.contains { $0.autor == "washington" && marca($0) == "Enviado" }
    }

    /// Fallos seguidos del canal SSE antes de pasar a la ruta liviana.
    static let fallosAntesDeRespaldo = 3
}
