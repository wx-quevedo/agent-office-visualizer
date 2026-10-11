import SwiftUI

/// Bandeja de Decisiones (boceto Decisiones): permisos, preguntas y atascos,
/// lo más urgente arriba, y lo resuelto hoy. Datos de GET /decisiones.
struct DecisionesVista: View {
    @Environment(ModeloApp.self) private var modelo
    @State private var bandeja: Bandeja?
    @State private var error: String?
    @State private var rechazando: Decision?
    @State private var motivo = ""
    @State private var enviando: String?
    @State private var errorAccion: String?
    @State private var todasResueltas = false
    private static let resueltasVisibles = 15

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Decisiones").font(.system(size: 34, weight: .bold))
                    Text("Todo lo que espera por ti, lo más urgente arriba.")
                        .font(.system(size: 15)).foregroundStyle(Color.texto2)
                }
                .padding(.top, 8)
                .padding(.bottom, 2)

                if let errorAccion {
                    Text(errorAccion).font(.system(size: 14)).foregroundStyle(Color.rojo)
                }

                if let b = bandeja {
                    let items = LogicaBandejas.ordenar(b.pendientes)
                    if items.isEmpty {
                        Tarjeta {
                            Text("Nada espera por ti ahora.")
                                .font(.system(size: 15)).foregroundStyle(Color.texto2)
                                .padding(16)
                        }
                    }
                    ForEach(items) { d in tarjeta(d) }
                    resueltas(b.resueltas_hoy)
                } else if let error {
                    Text(error).font(.system(size: 15)).foregroundStyle(Color.rojo)
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .refreshable { await leer() }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
        .task { await sondear() }
        // La misma consulta en vivo de la insignia: si cambia el conteo, se relee la bandeja.
        .onChange(of: modelo.pendientes) { Task { await leer() } }
        .alert("Rechazar el permiso", isPresented: Binding(get: { rechazando != nil }, set: { if !$0 { rechazando = nil } })) {
            TextField("Motivo (opcional)", text: $motivo)
            Button("Rechazar", role: .destructive) {
                if let d = rechazando { decidir(d, aprobar: false, motivo: motivo) }
                rechazando = nil
            }
            Button("Cancelar", role: .cancel) { rechazando = nil }
        } message: {
            Text("El agente recibe el motivo y puede intentar otra cosa.")
        }
    }

    private func sondear() async {
        while !Task.isCancelled {
            await leer()
            try? await Task.sleep(for: .seconds(10))
        }
    }

    private func leer() async {
        guard let api = modelo.api else { return }
        do {
            bandeja = try await api.decisiones()
            error = nil
        } catch ErrorAPI.sinSesion {
            modelo.sesionVencida()
        } catch let e as ErrorAPI {
            error = e.mensaje
        } catch {}
    }

    // MARK: - Tarjetas

    @ViewBuilder
    private func tarjeta(_ d: Decision) -> some View {
        let tono = LogicaBandejas.tono(d.tipo)
        let decidible = LogicaBandejas.sePuedeDecidir(d)
        Tarjeta(borde: d.tipo == "permiso" && decidible ? tono.color : tono.borde, grosor: d.tipo == "permiso" && decidible ? 2 : 1) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(LogicaBandejas.titulo(d).uppercased())
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(tono.color)
                        .lineLimit(1)
                    Spacer()
                    Text(LogicaBandejas.hace(d, ahora: modelo.ahora))
                        .font(.system(size: 13)).foregroundStyle(Color.texto2)
                }
                Text(LogicaBandejas.frase(d))
                    .font(.system(size: 15))
                    .fixedSize(horizontal: false, vertical: true)
                if let t = LogicaBandejas.detalleTecnico(d) {
                    Text(t)
                        .font(.mono(12))
                        .foregroundStyle(Color.texto3)
                        .lineLimit(5)
                        .padding(.horizontal, 10).padding(.vertical, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.fondo, in: RoundedRectangle(cornerRadius: 8))
                        .textSelection(.enabled)
                }
                switch d.tipo {
                case "permiso": accionesPermiso(d, decidible: decidible)
                case "pregunta": opcionesPregunta(d)
                case "atasco": accionesAtasco(d)
                default: EmptyView()
                }
            }
            .padding(14)
        }
        .accessibilityElement(children: .contain)
    }

    @ViewBuilder
    private func accionesPermiso(_ d: Decision, decidible: Bool) -> some View {
        if decidible {
            HStack(spacing: 8) {
                botonLleno("Aprobar", fondo: .acento) { decidir(d, aprobar: true, motivo: nil) }
                botonBorde("Rechazar") {
                    motivo = ""
                    rechazando = d
                }
            }
            .disabled(enviando == d.id)
            .opacity(enviando == d.id ? 0.6 : 1)
            if modelo.esPeligroso(herramienta: d.permiso?.herramienta ?? "", detalle: d.detalle ?? "") {
                Text("Comando marcado como peligroso: Aprobar pide Face ID.")
                    .font(.system(size: 12)).foregroundStyle(Color.texto2)
            }
        } else {
            Text("Responde en VS Code: esta solicitud no espera a la oficina.")
                .font(.system(size: 12)).foregroundStyle(Color.texto2)
        }
    }

    @ViewBuilder
    private func opcionesPregunta(_ d: Decision) -> some View {
        let preguntas = d.pregunta?.preguntas ?? []
        ForEach(Array(preguntas.enumerated()), id: \.offset) { n, q in
            VStack(alignment: .leading, spacing: 6) {
                if preguntas.count > 1 || (q.texto != LogicaBandejas.frase(d)) {
                    Text(q.encabezado.map { "\($0): \(q.texto)" } ?? q.texto)
                        .font(.system(size: 14, weight: .semibold))
                        .fixedSize(horizontal: false, vertical: true)
                }
                ForEach(Array(q.opciones.enumerated()), id: \.offset) { i, o in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(i + 1). \(o.etiqueta)").font(.system(size: 14))
                        if let desc = o.descripcion {
                            Text(desc).font(.system(size: 12)).foregroundStyle(Color.texto2)
                        }
                    }
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.bordeCampo))
                    .accessibilityLabel("Opción \(i + 1): \(o.etiqueta)")
                }
                if q.multiple == true {
                    Text("Se puede elegir más de una.").font(.system(size: 12)).foregroundStyle(Color.texto2)
                }
            }
            .padding(.top, n == 0 ? 0 : 6)
        }
        Label(LogicaBandejas.dondeResponder(d), systemImage: "desktopcomputer")
            .font(.system(size: 14, weight: .medium))
            .foregroundStyle(Color.naranja)
    }

    private func accionesAtasco(_ d: Decision) -> some View {
        HStack(spacing: 8) {
            botonLleno("Ver qué intentó", fondo: .texto3) { modelo.abrirFicha(d.session_id) }
            botonBorde("Ya lo vi") { yaLoVi(d) }
                .disabled(enviando == d.id)
        }
    }

    private func botonLleno(_ t: String, fondo: Color, accion: @escaping () -> Void) -> some View {
        Button(action: accion) {
            Text(t)
                .font(.system(size: 16, weight: .semibold))
                .frame(maxWidth: .infinity, minHeight: 44)
                .foregroundStyle(.white)
                .background(fondo, in: RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
    }

    private func botonBorde(_ t: String, accion: @escaping () -> Void) -> some View {
        Button(action: accion) {
            Text(t)
                .font(.system(size: 16, weight: .semibold))
                .frame(maxWidth: .infinity, minHeight: 44)
                .background(Color.white, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color(hex: 0x9AA0AA)))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Resueltas hoy

    @ViewBuilder
    private func resueltas(_ lista: [Resuelta]) -> some View {
        Rotulo(texto: "Resueltas hoy · \(lista.count)")
            .padding(.top, 8)
            .padding(.horizontal, 2)
        if !lista.isEmpty {
            Tarjeta {
                VStack(spacing: 0) {
                    let visibles = todasResueltas ? lista : Array(lista.prefix(Self.resueltasVisibles))
                    ForEach(Array(visibles.enumerated()), id: \.element.id) { i, r in
                        if i > 0 { Divider().overlay(Color.separador) }
                        let tono = LogicaBandejas.tono(resuelta: r)
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Text(Logica.horaMinuto(r.cuando))
                                .font(.mono(12)).foregroundStyle(Color.texto2)
                                .frame(width: 42, alignment: .leading)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(LogicaBandejas.texto(resuelta: r)).font(.system(size: 14)).lineLimit(3)
                                if let m = r.motivo, !m.isEmpty {
                                    Text("Motivo: \(m)").font(.system(size: 12)).foregroundStyle(Color.texto2)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            Text(r.como ?? "")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(tono.color)
                                .multilineTextAlignment(.trailing)
                        }
                        .padding(.horizontal, 14).padding(.vertical, 10)
                    }
                    if lista.count > Self.resueltasVisibles {
                        Divider().overlay(Color.separador)
                        Button(todasResueltas ? "Mostrar menos" : "Mostrar las \(lista.count)") {
                            todasResueltas.toggle()
                        }
                        .font(.system(size: 15, weight: .medium))
                        .frame(maxWidth: .infinity, minHeight: 44)
                    }
                }
            }
        }
    }

    // MARK: - Acciones

    private func decidir(_ d: Decision, aprobar: Bool, motivo: String?) {
        guard let id = d.permiso?.id else { return }
        errorAccion = nil
        enviando = d.id
        Task {
            defer { enviando = nil }
            do {
                try await modelo.decidir(id: id, herramienta: d.permiso?.herramienta ?? "", detalle: d.detalle ?? "",
                                         aprobar: aprobar, motivo: motivo)
            } catch let e as ErrorAPI {
                errorAccion = e.mensaje
            } catch {
                errorAccion = ErrorAPI.red.mensaje
            }
            await leer()
        }
    }

    private func yaLoVi(_ d: Decision) {
        errorAccion = nil
        enviando = d.id
        Task {
            defer { enviando = nil }
            do {
                try await modelo.api?.atascoVisto(d.id)
            } catch let e as ErrorAPI {
                errorAccion = e.mensaje
            } catch {}
            await leer()
            await modelo.leerUnaVez()
        }
    }
}
