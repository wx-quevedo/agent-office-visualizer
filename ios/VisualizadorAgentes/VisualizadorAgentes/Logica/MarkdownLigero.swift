import Foundation

/// Markdown ligero para las burbujas del chat: párrafos, títulos, listas y
/// bloques de código, con negritas, cursivas, código y enlaces dentro de cada
/// línea (AttributedString). El HTML nunca se muestra crudo: las etiquetas se
/// quitan y las entidades comunes se traducen.
enum MarkdownLigero {
    enum Bloque: Equatable {
        case parrafo(String)
        case titulo(String)
        case vineta(String)
        case numerada(Int, String)
        case codigo(String)
    }

    static func bloques(_ texto: String) -> [Bloque] {
        var salida: [Bloque] = []
        var parrafo: [String] = []
        var codigo: [String]?

        func cerrarParrafo() {
            if !parrafo.isEmpty { salida.append(.parrafo(parrafo.joined(separator: "\n"))) }
            parrafo = []
        }

        for cruda in texto.replacingOccurrences(of: "\r\n", with: "\n").components(separatedBy: "\n") {
            let linea = cruda.trimmingCharacters(in: .whitespaces)
            if linea.hasPrefix("```") {
                if let c = codigo {
                    salida.append(.codigo(c.joined(separator: "\n")))
                    codigo = nil
                } else {
                    cerrarParrafo()
                    codigo = []
                }
                continue
            }
            if codigo != nil {
                codigo?.append(cruda)
                continue
            }
            let l = sinHTML(linea)
            if l.isEmpty {
                cerrarParrafo()
            } else if let r = l.range(of: #"^#{1,6}\s+"#, options: .regularExpression) {
                cerrarParrafo()
                salida.append(.titulo(String(l[r.upperBound...])))
            } else if let r = l.range(of: #"^[-*•]\s+"#, options: .regularExpression) {
                cerrarParrafo()
                salida.append(.vineta(String(l[r.upperBound...])))
            } else if let r = l.range(of: #"^\d{1,3}[.)]\s+"#, options: .regularExpression) {
                cerrarParrafo()
                let n = Int(l.prefix { $0.isNumber }) ?? 1
                salida.append(.numerada(n, String(l[r.upperBound...])))
            } else {
                parrafo.append(l)
            }
        }
        if let c = codigo { salida.append(.codigo(c.joined(separator: "\n"))) }
        cerrarParrafo()
        return salida
    }

    /// Quita las etiquetas HTML y traduce las entidades más comunes.
    static func sinHTML(_ s: String) -> String {
        guard s.contains("<") || s.contains("&") else { return s }
        var t = s.replacingOccurrences(of: #"<br\s*/?>"#, with: " ", options: [.regularExpression, .caseInsensitive])
        t = t.replacingOccurrences(of: #"</?[A-Za-z][^>]*>"#, with: "", options: .regularExpression)
        for (e, c) in [("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", "\""), ("&#39;", "'"), ("&amp;", "&")] {
            t = t.replacingOccurrences(of: e, with: c)
        }
        return t
    }

    /// Una línea con su formato (negritas, cursivas, `código`, enlaces).
    static func enLinea(_ s: String) -> AttributedString {
        let opciones = AttributedString.MarkdownParsingOptions(
            allowsExtendedAttributes: false, interpretedSyntax: .inlineOnlyPreservingWhitespace,
            failurePolicy: .returnPartiallyParsedIfPossible)
        return (try? AttributedString(markdown: s, options: opciones)) ?? AttributedString(s)
    }
}
