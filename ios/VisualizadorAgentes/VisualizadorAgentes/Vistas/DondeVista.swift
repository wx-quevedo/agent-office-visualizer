import SwiftUI

/// "Dónde quedamos" de un proyecto (boceto Donde, ahora dentro de cada proyecto):
/// plan por etapas, dónde estás, lo último y lo que espera tu decisión.
/// Datos de /proyectos y /consumo (los lee ModeloApp).
struct DondeDetalle: View {
    @Environment(ModeloApp.self) private var modelo
    let proyecto: ProyectoVista?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if let p = proyecto {
                    detalle(p)
                } else if modelo.proyectosMonitor == nil {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
                } else {
                    Tarjeta {
                        Text("Este proyecto todavía no tiene PROJECT.md o su máquina aún no lo envió.")
                            .font(.system(size: 15)).foregroundStyle(Color.texto2).padding(16)
                    }
                    .padding(.horizontal, 16)
                }
            }
            .padding(.top, 4)
            .padding(.bottom, 24)
        }
        .refreshable { await modelo.leerProyectos() }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
    }

    @ViewBuilder
    private func detalle(_ p: ProyectoVista) -> some View {
        let d = p.datos
        let segundos = LogicaDonde.segundosHoy(modelo.consumo, carpeta: d.carpeta)
        let linea = [p.ultima.map { Logica.cuando($0, ahora: modelo.ahora) } ?? "Sin fecha",
                     segundos.flatMap { $0 > 0 ? "\(Logica.tiempoCorto($0)) de agentes" : nil }]
            .compactMap { $0 }.joined(separator: " · ")
        VStack(alignment: .leading, spacing: 10) {
            VStack(alignment: .leading, spacing: 2) {
                Text(p.nombre).font(.system(size: 20, weight: .semibold))
                Text(linea).font(.system(size: 13)).foregroundStyle(Color.texto2)
            }
            .padding(.top, 4)

            if !d.tiene_project_md {
                Tarjeta {
                    Text("Este proyecto no tiene PROJECT.md: no hay plan ni posición anotados.")
                        .font(.system(size: 15)).padding(16)
                }
            } else {
                etapas(d)
                estasAqui(d)
            }
            if let c = d.ultimo_commit {
                Tarjeta {
                    VStack(alignment: .leading, spacing: 4) {
                        Rotulo(texto: "Lo último")
                        Text(c.mensaje ?? "Commit sin mensaje").font(.system(size: 15))
                        Text([String(c.hash.prefix(7)), c.fecha.map { Logica.cuando($0, ahora: modelo.ahora) }]
                            .compactMap { $0 }.joined(separator: " · "))
                            .font(.mono(12)).foregroundStyle(Color.texto2)
                    }
                    .padding(.horizontal, 16).padding(.vertical, 14)
                }
            }
            if !d.espera_decision.isEmpty {
                Tarjeta(borde: .bordeNaranja) {
                    VStack(alignment: .leading, spacing: 6) {
                        Rotulo(texto: "Espera tu decisión · \(d.espera_decision.count)", color: .naranja)
                        ForEach(Array(d.espera_decision.enumerated()), id: \.offset) { _, t in
                            Text(t).font(.system(size: 15))
                        }
                    }
                    .padding(.horizontal, 16).padding(.vertical, 14)
                }
            }
            let atentos = p.agentes.filter { $0.estado.numero != 21 && (Logica.grupo($0.estado.numero) == .espera || $0.atasco != nil) }
            if !atentos.isEmpty {
                Tarjeta(borde: .bordeAzul) {
                    VStack(alignment: .leading, spacing: 0) {
                        Rotulo(texto: "Agentes que te esperan", color: .acento)
                            .padding(.horizontal, 16).padding(.top, 12).padding(.bottom, 4)
                        ForEach(atentos) { a in
                            Button { modelo.abrirFicha(a.id) } label: {
                                HStack {
                                    Text(Logica.loQuePide(a)).font(.system(size: 15)).lineLimit(2)
                                    Spacer()
                                    Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold))
                                        .foregroundStyle(Color.bordeCampo)
                                }
                                .padding(.horizontal, 16).padding(.vertical, 10)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.bottom, 4)
                }
            }
        }
        .padding(.horizontal, 16)
    }

    @ViewBuilder
    private func etapas(_ d: ProyectoApi) -> some View {
        let lista = LogicaDonde.etapas(d.plan, posicion: d.posicion)
        if !lista.isEmpty {
            let actual = lista.firstIndex { $0.estado == .actual }
            VStack(alignment: .leading, spacing: 8) {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: min(max(lista.count, 1), 9)), spacing: 4) {
                    ForEach(lista) { e in
                        let (fondo, borde, letra): (Color, Color, Color) = switch e.estado {
                        case .hecha: (.texto3, .texto3, .white)
                        case .actual: (.fondoActual, .acento, .acento)
                        case .pendiente: (.white, .bordeCampo, .gris)
                        }
                        Text(e.corto)
                            .font(.system(size: 13, weight: .semibold))
                            .lineLimit(1).minimumScaleFactor(0.6)
                            .foregroundStyle(letra)
                            .frame(maxWidth: .infinity, minHeight: 34)
                            .background(fondo, in: RoundedRectangle(cornerRadius: 7))
                            .overlay(RoundedRectangle(cornerRadius: 7).strokeBorder(borde, lineWidth: 2))
                            .accessibilityLabel("\(e.etiqueta), \(e.estado == .hecha ? "hecha" : e.estado == .actual ? "actual" : "pendiente")")
                    }
                }
                if let i = actual {
                    Text("\(lista[i].etiqueta) de \(lista.count) · \(lista[i].nombre)")
                        .font(.system(size: 14)).foregroundStyle(Color.texto3)
                }
            }
            .padding(.top, 4)
        }
    }

    private func estasAqui(_ d: ProyectoApi) -> some View {
        let prompt = LogicaDonde.promptsDeEtapa(d).first { $0.actual }
        let titulo = prompt.map { "Prompt \($0.numero)" + ($0.nombre.isEmpty ? "" : " · \($0.nombre)") }
            ?? d.posicion ?? "Sin posición anotada"
        let siguiente = d.siguiente_paso.map { s in
            ["Lo siguiente: \(s)", LogicaDonde.quienHace(s)].compactMap { $0 }.joined(separator: " ")
        }
        return Tarjeta(borde: .acento, grosor: 2) {
            VStack(alignment: .leading, spacing: 6) {
                Text("ESTÁS AQUÍ")
                    .font(.system(size: 11, weight: .bold)).tracking(0.5)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .foregroundStyle(.white)
                    .background(Color.acento, in: RoundedRectangle(cornerRadius: 5))
                Text(titulo).font(.system(size: 17, weight: .semibold))
                if let siguiente {
                    Text(siguiente).font(.system(size: 14)).foregroundStyle(Color.texto3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(16)
        }
    }
}
