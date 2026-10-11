import SwiftUI

/// Ficha del agente (boceto Ficha): permiso o pregunta, ahora mismo, cifras y turnos de hoy.
struct FichaVista: View {
    @Environment(ModeloApp.self) private var modelo
    let id: String
    @State private var historial: Historial?
    @State private var consumo: Consumo?
    @State private var verHistorial = false

    var body: some View {
        Group {
            if let a = modelo.agente(id) {
                contenido(a)
            } else if modelo.estado == nil {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView("El agente ya no está en la oficina", systemImage: "person.crop.circle.badge.questionmark",
                                       description: Text("Se cerró hace más de una hora o el servidor lo olvidó."))
            }
        }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
        .toolbar(.visible, for: .navigationBar)
        .navigationBarTitleDisplayMode(.inline)
        .task(id: id) { await cargar() }
        .sheet(isPresented: $verHistorial) {
            if let c = modelo.credencial {
                NavigationStack {
                    PaginaWeb(url: URL(string: c.servidor.absoluteString + "/historial?agente=\(id)")!, credencial: c)
                        .ignoresSafeArea(edges: .bottom)
                        .navigationTitle("Historial")
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar { Button("Listo") { verHistorial = false } }
                }
            }
        }
    }

    /// Turnos (30 s) y consumo (60 s), como la ficha de la web.
    private func cargar() async {
        var vuelta = 0
        while !Task.isCancelled {
            if let api = modelo.api {
                if let h = try? await api.historial(sesion: id, porPagina: 20) { historial = h }
                if vuelta % 2 == 0, let c = try? await api.consumo() { consumo = c }
            }
            vuelta += 1
            try? await Task.sleep(for: .seconds(30))
        }
    }

    @ViewBuilder
    private func contenido(_ a: Agente) -> some View {
        let nombre = Logica.nombre(a)
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 12) {
                    Iniciales(texto: Logica.iniciales(nombre), tamano: 52)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(nombre).font(.system(size: 24, weight: .bold)).lineLimit(1).minimumScaleFactor(0.7)
                        Text(Logica.subtitulo(a)).font(.system(size: 13)).foregroundStyle(Color.texto2)
                    }
                }
                .padding(.bottom, 0)

                TarjetaEspera(agente: a)

                ahoraMismo(a)

                HStack(spacing: 8) {
                    ForEach(Logica.cifras(a, tokens: Logica.tokensHoy(consumo, sesion: a.id), ahora: modelo.ahora)) { c in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(c.titulo).font(.system(size: 12)).foregroundStyle(Color.texto2)
                            Text(c.valor)
                                .font(.mono(16, .medium))
                                .foregroundStyle(c.alerta ? Color.rojo : Color.texto)
                                .lineLimit(1)
                                .minimumScaleFactor(0.7)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                    }
                }

                turnos()

                HStack(spacing: 10) {
                    boton("Historial") { verHistorial = true }
                    boton("Dónde quedamos") { modelo.abrirDonde(carpeta: a.agente.proyecto) }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 4)
            .padding(.bottom, 24)
        }
    }

    private func ahoraMismo(_ a: Agente) -> some View {
        let am = Logica.ahoraMismo(a, ahora: modelo.ahora)
        return Tarjeta {
            VStack(alignment: .leading, spacing: 4) {
                Rotulo(texto: "Ahora mismo")
                HStack(alignment: .firstTextBaseline) {
                    Text(am.texto).font(.system(size: 18, weight: .semibold))
                    Spacer(minLength: 8)
                    Text(am.tiempo).font(.mono(15))
                }
                if let r = am.razonable {
                    Text(r).font(.system(size: 13)).foregroundStyle(Color.texto2)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
        }
    }

    private func turnos() -> some View {
        let hoy = Logica.turnosDeHoy(historial?.turnos ?? [], ahora: modelo.ahora)
        return Tarjeta {
            VStack(alignment: .leading, spacing: 0) {
                Rotulo(texto: "Turnos de hoy")
                    .padding(.horizontal, 16)
                    .padding(.top, 12)
                    .padding(.bottom, 4)
                if historial == nil {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 12)
                } else if hoy.isEmpty {
                    Text("Sin turnos hoy.")
                        .font(.system(size: 14))
                        .foregroundStyle(Color.texto2)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                }
                ForEach(hoy, id: \.numero) { t in
                    let r = Logica.resultado(t.resultado)
                    Divider().overlay(Color.separador)
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text(Logica.horaMinuto(t.inicio))
                            .font(.mono(12))
                            .foregroundStyle(Color.texto2)
                            .frame(width: 42, alignment: .leading)
                        Text(t.pedido ?? "(trabajo sin pedido visible)")
                            .font(.system(size: 14))
                            .lineLimit(2)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text(r.texto)
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(r.tono.color)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                }
            }
            .padding(.bottom, 4)
        }
    }

    private func boton(_ titulo: String, accion: @escaping () -> Void) -> some View {
        Button(action: accion) {
            Text(titulo)
                .font(.system(size: 15, weight: .medium))
                .frame(maxWidth: .infinity, minHeight: 46)
                .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.bordeCampo))
        }
        .buttonStyle(.plain)
    }
}

/// Permiso (con Aprobar y Rechazar) o pregunta pendiente.
struct TarjetaEspera: View {
    @Environment(ModeloApp.self) private var modelo
    let agente: Agente
    @State private var enviando = false
    @State private var error: String?

    var body: some View {
        if agente.estado.numero == 13 || agente.permiso.map(Logica.sePuedeDecidir) == true {
            permiso()
        } else if agente.estado.numero == 14 || agente.pregunta_pendiente != nil {
            pregunta()
        } else if let at = agente.atasco, agente.estado.numero != 21 {
            atasco(at)
        }
    }

    private var hace: String { Logica.hace(agente.permiso?.creada ?? agente.estado.desde, ahora: modelo.ahora) }

    private func permiso() -> some View {
        let p = agente.permiso
        let decidible = Logica.sePuedeDecidir(p)
        let peligroso = p.map(modelo.esPeligroso) ?? false
        return Tarjeta(borde: .acento, grosor: 2) {
            VStack(alignment: .leading, spacing: 10) {
                Rotulo(texto: "Te pide permiso · \(hace)", color: .acento)
                Text(Logica.loQuePide(agente)).font(.system(size: 17)).fixedSize(horizontal: false, vertical: true)
                if let d = p?.detalle, !d.isEmpty {
                    Text(d)
                        .font(.mono(12))
                        .foregroundStyle(Color.texto3)
                        .lineLimit(6)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.fondo, in: RoundedRectangle(cornerRadius: 8))
                        .textSelection(.enabled)
                }
                if let p, decidible {
                    HStack(spacing: 10) {
                        Button { decidir(p, aprobar: true) } label: {
                            Text("Aprobar")
                                .font(.system(size: 17, weight: .semibold))
                                .frame(maxWidth: .infinity, minHeight: 50)
                                .foregroundStyle(.white)
                                .background(Color.acento, in: RoundedRectangle(cornerRadius: 12))
                        }
                        Button { decidir(p, aprobar: false) } label: {
                            Text("Rechazar")
                                .font(.system(size: 17, weight: .semibold))
                                .frame(maxWidth: .infinity, minHeight: 50)
                                .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color(hex: 0x9AA0AA)))
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(enviando)
                    .opacity(enviando ? 0.6 : 1)
                    if peligroso {
                        Text("Comando marcado como peligroso: Aprobar pide Face ID.")
                            .font(.system(size: 12)).foregroundStyle(Color.texto2)
                    }
                } else if let p {
                    Text(Logica.textoSinBotones(p)).font(.system(size: 13)).foregroundStyle(Color.texto2)
                } else {
                    Text("Responde en VS Code.").font(.system(size: 13)).foregroundStyle(Color.texto2)
                }
                if let error {
                    Text(error).font(.system(size: 13)).foregroundStyle(Color.rojo)
                }
            }
            .padding(16)
        }
    }

    private func pregunta() -> some View {
        Tarjeta(borde: .naranja, grosor: 2) {
            VStack(alignment: .leading, spacing: 10) {
                Rotulo(texto: "Espera tu respuesta · \(hace)", color: .naranja)
                Text(agente.pregunta_pendiente ?? Logica.loQuePide(agente))
                    .font(.system(size: 17))
                    .fixedSize(horizontal: false, vertical: true)
                Text("Responde en VS Code. Responder desde la app llega en el Prompt 33.")
                    .font(.system(size: 12)).foregroundStyle(Color.texto2)
            }
            .padding(16)
        }
    }

    private func atasco(_ at: Agente.Atasco) -> some View {
        Tarjeta(borde: .rojo, grosor: 2) {
            VStack(alignment: .leading, spacing: 8) {
                Rotulo(texto: "Parece atascado · \(Logica.hace(at.desde, ahora: modelo.ahora))", color: .rojo)
                Text(Logica.resumen(agente, "atasco") ?? at.motivo).font(.system(size: 16))
                if let e = at.ultimo_error, !e.isEmpty {
                    Text(e).font(.mono(12)).foregroundStyle(Color.texto3).lineLimit(4)
                }
            }
            .padding(16)
        }
    }

    private func decidir(_ p: Permiso, aprobar: Bool) {
        error = nil
        enviando = true
        Task {
            defer { enviando = false }
            do {
                try await modelo.decidir(p, aprobar: aprobar)
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {
                self.error = ErrorAPI.red.mensaje
            }
        }
    }
}
