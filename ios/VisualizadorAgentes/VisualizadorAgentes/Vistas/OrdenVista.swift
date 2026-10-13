import SwiftUI

extension Color {
    static let morado = Color(hex: 0x5B3FA8)
    static let bordeMorado = Color(hex: 0xC9BDEB)
    static let grisBoton = Color(hex: 0x9AA0AA)
}

extension TonoProyecto {
    var color: Color {
        switch self {
        case .morado: return .morado
        case .verde: return .verde
        case .rojo: return .rojo
        case .azul: return .acento
        case .gris: return .texto2
        }
    }

    var borde: Color {
        switch self {
        case .morado: return .bordeMorado
        case .rojo: return .bordeRojo
        default: return .borde
        }
    }
}

/// Texto con markdown ligero (negritas, listas, código). Nunca muestra HTML crudo.
struct TextoMarkdown: View {
    let texto: String
    var tamano: CGFloat = 15
    var color: Color = .texto

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(MarkdownLigero.bloques(texto).enumerated()), id: \.offset) { _, b in
                switch b {
                case .parrafo(let t):
                    Text(MarkdownLigero.enLinea(t)).font(.system(size: tamano))
                case .titulo(let t):
                    Text(MarkdownLigero.enLinea(t)).font(.system(size: tamano + 1, weight: .bold))
                case .vineta(let t):
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text("•").font(.system(size: tamano))
                        Text(MarkdownLigero.enLinea(t)).font(.system(size: tamano))
                    }
                case .numerada(let n, let t):
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text("\(n).").font(.system(size: tamano)).monospacedDigit()
                        Text(MarkdownLigero.enLinea(t)).font(.system(size: tamano))
                    }
                case .codigo(let t):
                    ScrollView(.horizontal, showsIndicators: false) {
                        Text(t).font(.mono(12)).foregroundStyle(Color.texto3).fixedSize()
                    }
                    .padding(.horizontal, 10).padding(.vertical, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.fondo, in: RoundedRectangle(cornerRadius: 8))
                }
            }
        }
        .foregroundStyle(color)
        .tint(color == .white ? .white : .acento)
        .fixedSize(horizontal: false, vertical: true)
        .textSelection(.enabled)
    }
}

/// Tarjeta de una orden del orquestador (boceto Chat): estimado, dificultad y,
/// si está por aprobar, Aprobar, Editar y Rechazar. Rechazar pide el motivo;
/// Editar abre el texto y aprueba la versión editada.
struct TarjetaOrden: View {
    @Environment(ModeloApp.self) private var modelo
    let orden: Orden
    /// Se llegó desde su aviso (Responder): la tarjeta se resalta.
    var resaltada = false
    /// Lo que devolvió el servidor tras decidir (para mostrarlo al instante).
    var alCambiar: (Orden) -> Void = { _ in }

    @State private var enviando = false
    @State private var error: String?
    @State private var rechazando = false
    @State private var motivo = ""
    @State private var editando = false
    @State private var completa = false

    var body: some View {
        let estado = LogicaProyectos.estadoOrden(orden.estado)
        let porAprobar = orden.estado == "por_aprobar"
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text("ORDEN \(orden.numero) PARA \(orden.agente.uppercased())")
                    .font(.system(size: 12, weight: .bold)).tracking(0.4)
                    .foregroundStyle(porAprobar ? Color.morado : Color.texto2)
                    .lineLimit(1)
                Spacer(minLength: 6)
                Text(estado.texto).font(.system(size: 12, weight: .medium)).foregroundStyle(estado.tono.color)
            }
            Text(LogicaProyectos.tituloCorto(orden))
                .font(.system(size: 15, weight: .semibold))
                .fixedSize(horizontal: false, vertical: true)
            TextoMarkdown(texto: orden.texto, tamano: 14, color: .texto3)
                .lineLimit(completa ? nil : 6)
                .frame(maxHeight: completa ? nil : 150, alignment: .top)
                .clipped()
            if orden.texto.count > 380 || orden.texto.split(separator: "\n").count > 6 {
                Button(completa ? "Ver menos" : "Ver la orden completa") { completa.toggle() }
                    .font(.system(size: 13)).buttonStyle(.plain).foregroundStyle(Color.acento)
            }
            if let ed = LogicaProyectos.estimadoYDificultad(orden) {
                Text(ed).font(.system(size: 12)).foregroundStyle(Color.texto2)
            }
            if porAprobar {
                HStack(spacing: 8) {
                    boton("Aprobar", lleno: true) { aprobar(texto: nil) }
                    boton("Editar") { editando = true }
                    boton("Rechazar") {
                        motivo = ""
                        rechazando = true
                    }
                }
                .disabled(enviando)
                .opacity(enviando ? 0.6 : 1)
            } else {
                decision
            }
            if let error {
                Text(error).font(.system(size: 13)).foregroundStyle(Color.rojo)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(porAprobar ? Color.morado : Color.borde, lineWidth: porAprobar ? 2 : 1))
        .background(RoundedRectangle(cornerRadius: 17).fill(resaltada ? Color.bordeMorado : Color.clear).padding(-3))
        .alert("Rechazar la orden", isPresented: $rechazando) {
            TextField("Motivo", text: $motivo)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Button("Rechazar", role: .destructive) {
                if let m = LogicaProyectos.motivoValido(motivo) { rechazar(m) } else { error = "Escribe el motivo para rechazarla." }
            }
            Button("Cancelar", role: .cancel) {}
        } message: {
            Text("El orquestador recibe el motivo y puede proponer otra orden.")
        }
        .sheet(isPresented: $editando) {
            EditarOrden(orden: orden) { texto in aprobar(texto: texto) }
        }
    }

    @ViewBuilder
    private var decision: some View {
        let partes = [LogicaProyectos.quienDecidio(orden.decidido_por), orden.decidido.map { Logica.cuando($0, ahora: modelo.ahora) }]
            .compactMap { $0 }
        if !partes.isEmpty || orden.motivo != nil || orden.resumen != nil {
            VStack(alignment: .leading, spacing: 3) {
                if !partes.isEmpty {
                    Text(partes.joined(separator: " · ") + (orden.editada == true ? " · con cambios" : ""))
                        .font(.system(size: 12)).foregroundStyle(Color.texto2)
                }
                if let m = orden.motivo, !m.isEmpty {
                    Text("Motivo: \(m)").font(.system(size: 13)).foregroundStyle(Color.texto3)
                }
                if let r = orden.resumen, !r.isEmpty {
                    TextoMarkdown(texto: r, tamano: 13, color: .texto3)
                }
            }
        }
    }

    private func boton(_ t: String, lleno: Bool = false, accion: @escaping () -> Void) -> some View {
        Button(action: accion) {
            Text(t)
                .font(.system(size: 15, weight: .semibold))
                .frame(maxWidth: .infinity, minHeight: 44)
                .foregroundStyle(lleno ? Color.white : Color.texto)
                .background(lleno ? Color.morado : Color.white, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(lleno ? Color.clear : Color.grisBoton))
        }
        .buttonStyle(.plain)
    }

    private func aprobar(texto: String?) {
        hacer { api in try await api.aprobarOrden(orden.id, texto: texto.flatMap { LogicaProyectos.textoEditado(orden, $0) }) }
    }

    private func rechazar(_ motivo: String) {
        hacer { api in try await api.rechazarOrden(orden.id, motivo: motivo) }
    }

    private func hacer(_ paso: @escaping (ClienteAPI) async throws -> Orden) {
        guard let api = modelo.api else { return }
        error = nil
        enviando = true
        Task {
            defer { enviando = false }
            do {
                let o = try await paso(api)
                alCambiar(o)
                await modelo.leerUnaVez()
                await modelo.leerProyectos(todo: false)
            } catch ErrorAPI.sinSesion {
                modelo.sesionVencida()
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {
                self.error = ErrorAPI.red.mensaje
            }
        }
    }
}

/// Editar el texto de una orden antes de aprobarla.
struct EditarOrden: View {
    let orden: Orden
    let aprobar: (String) -> Void
    @State private var texto = ""
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 8) {
                Text(LogicaProyectos.tituloOrden(orden)).font(.system(size: 13, weight: .semibold)).foregroundStyle(Color.texto2)
                TextEditor(text: $texto)
                    .font(.system(size: 15))
                    .padding(8)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.bordeCampo))
                Text("Al aprobar, el agente recibe este texto en lugar de la propuesta del orquestador.")
                    .font(.system(size: 12)).foregroundStyle(Color.texto2)
            }
            .padding(16)
            .background(Color.fondo)
            .navigationTitle("Editar la orden")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancelar") { cerrar() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Aprobar") {
                        aprobar(texto)
                        cerrar()
                    }
                    .disabled(texto.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
        .onAppear { texto = orden.texto }
    }
}
