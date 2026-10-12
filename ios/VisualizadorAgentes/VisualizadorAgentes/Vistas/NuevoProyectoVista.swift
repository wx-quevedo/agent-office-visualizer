import SwiftUI

/// Nuevo proyecto (boceto Nuevo): nombre, máquina, cuenta, plantilla, equipo
/// (orquestador y agentes de código con modelo y esfuerzo) y aprobación
/// automática. POST /proyectos-creados, igual que la web.
struct NuevoProyectoVista: View {
    @Environment(ModeloApp.self) private var modelo
    @Environment(\.dismiss) private var cerrar
    let creado: (ProyectoEquipo) -> Void

    @State private var nombre = ""
    @State private var maquinas: [MaquinaEquipo]?
    @State private var maquina = ""
    @State private var cuenta = "personal"
    @State private var plantilla = "vacia"
    @State private var orquestador = NuevoProyecto.Config(modelo: "opus", esfuerzo: "high")
    @State private var agentes = [NuevoProyecto.Config(modelo: "sonnet", esfuerzo: "medium")]
    @State private var autoAprobar = false
    @State private var editando: Int? // -1 orquestador, 0... agentes
    @State private var creando = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    seccionNombre
                    seccionMaquina
                    seccionPlantilla
                    seccionEquipo
                    Tarjeta {
                        Toggle(isOn: $autoAprobar) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Aprobar órdenes automáticamente").font(.system(size: 15))
                                Text(autoAprobar ? "Encendido: las órdenes llegan al agente sin pasar por ti."
                                     : "Apagado: apruebas cada orden del orquestador al agente.")
                                    .font(.system(size: 12)).foregroundStyle(Color.texto2)
                            }
                        }
                        .tint(.verde)
                        .padding(.horizontal, 14).padding(.vertical, 12)
                    }
                    if let error { Text(error).font(.system(size: 14)).foregroundStyle(Color.rojo) }
                }
                .padding(.horizontal, 16)
                .padding(.top, 6)
                .padding(.bottom, 12)
            }
            .scrollDismissesKeyboard(.interactively)
            .safeAreaInset(edge: .bottom) {
                Button(action: crear) {
                    Group {
                        if creando { ProgressView().tint(.white) } else { Text("Crear y empezar la entrevista") }
                    }
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity, minHeight: 52)
                    .background(Color.acento, in: RoundedRectangle(cornerRadius: 14))
                }
                .buttonStyle(.plain)
                .disabled(!puedeCrear || creando)
                .opacity(puedeCrear ? 1 : 0.5)
                .padding(.horizontal, 16).padding(.vertical, 10)
                .background(Color.fondo)
            }
            .background(Color.fondo)
            .foregroundStyle(Color.texto)
            .navigationTitle("Nuevo proyecto")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancelar") { cerrar() } } }
            .task { await leerMaquinas() }
            .sheet(item: Binding(get: { editando.map(Editando.init) }, set: { editando = $0?.indice })) { e in
                ElegirModelo(titulo: e.indice < 0 ? "Orquestador" : "Agente de código",
                             config: e.indice < 0 ? orquestador
                                 : (agentes.indices.contains(e.indice) ? agentes[e.indice] : NuevoProyecto.Config(modelo: "sonnet", esfuerzo: "medium")),
                             quitar: e.indice > 0 ? { if agentes.indices.contains(e.indice) { agentes.remove(at: e.indice) } } : nil) { nueva in
                    if e.indice < 0 { orquestador = nueva } else if agentes.indices.contains(e.indice) { agentes[e.indice] = nueva }
                }
                .presentationDetents([.medium])
            }
        }
    }

    private struct Editando: Identifiable {
        let indice: Int
        var id: Int { indice }
    }

    private var maquinaElegida: MaquinaEquipo? { maquinas?.first { $0.id == maquina } }

    private var puedeCrear: Bool {
        LogicaProyectos.errorNombre(nombre.trimmingCharacters(in: .whitespaces)) == nil
            && maquinaElegida?.disponible == true && !agentes.isEmpty
    }

    private var seccionNombre: some View {
        let n = nombre.trimmingCharacters(in: .whitespaces)
        let err = n.isEmpty ? nil : LogicaProyectos.errorNombre(n)
        return Tarjeta {
            VStack(alignment: .leading, spacing: 6) {
                Rotulo(texto: "Nombre").font(.system(size: 12, weight: .semibold))
                TextField("landing-inmersoft", text: $nombre)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .font(.system(size: 16))
                    .padding(.horizontal, 12).frame(height: 40)
                    .overlay(RoundedRectangle(cornerRadius: 9).strokeBorder(err == nil ? Color.bordeCampo : Color.rojo))
                if let err {
                    Text(err).font(.system(size: 12)).foregroundStyle(Color.rojo)
                } else if let ruta = LogicaProyectos.rutaNueva(maquinaElegida?.ruta_base, n.isEmpty ? "nombre" : n) {
                    Text(ruta).font(.mono(12)).foregroundStyle(Color.texto2)
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
        }
    }

    private var seccionMaquina: some View {
        Tarjeta {
            VStack(alignment: .leading, spacing: 10) {
                Rotulo(texto: "Dónde y con qué cuenta").font(.system(size: 12, weight: .semibold))
                if let maquinas {
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)], spacing: 8) {
                        ForEach(maquinas) { m in
                            let on = m.id == maquina
                            Button { if m.disponible { maquina = m.id } } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(m.nombre).font(.system(size: 15, weight: .semibold)).lineLimit(1)
                                    Text(m.disponible ? "Encendida" : (m.motivo ?? "No disponible"))
                                        .font(.system(size: 12)).foregroundStyle(m.disponible ? Color.verde : Color.texto2)
                                        .lineLimit(2).multilineTextAlignment(.leading)
                                }
                                .padding(.horizontal, 10).padding(.vertical, 6)
                                .frame(maxWidth: .infinity, minHeight: 52, alignment: .leading)
                                .background(on ? Color.fondoActual : Color.white, in: RoundedRectangle(cornerRadius: 10))
                                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(on ? Color.acento : Color.bordeCampo, lineWidth: on ? 2 : 1))
                            }
                            .buttonStyle(.plain)
                            .opacity(m.disponible ? 1 : 0.7)
                        }
                    }
                    if maquinas.isEmpty {
                        Text("No hay máquinas registradas.").font(.system(size: 14)).foregroundStyle(Color.texto2)
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
                Picker("Cuenta", selection: $cuenta) {
                    Text("Personal").tag("personal")
                    Text("Demo Org").tag("demo")
                }
                .pickerStyle(.segmented)
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
        }
    }

    private var seccionPlantilla: some View {
        Tarjeta {
            VStack(alignment: .leading, spacing: 8) {
                Rotulo(texto: "Plantilla").font(.system(size: 12, weight: .semibold))
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(LogicaProyectos.plantillas, id: \.valor) { t in
                            let on = t.valor == plantilla
                            Button { plantilla = t.valor } label: {
                                Text(t.texto).font(.system(size: 14))
                                    .padding(.horizontal, 12).frame(height: 34)
                                    .foregroundStyle(on ? Color.white : Color.texto)
                                    .background(on ? Color.acento : Color.white, in: Capsule())
                                    .overlay(Capsule().strokeBorder(on ? Color.acento : Color.bordeCampo))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
        }
    }

    private var seccionEquipo: some View {
        Tarjeta {
            VStack(alignment: .leading, spacing: 0) {
                Rotulo(texto: "Equipo").font(.system(size: 12, weight: .semibold))
                    .padding(.horizontal, 14).padding(.top, 12).padding(.bottom, 4)
                filaMiembro("OR", "Orquestador", orquestador, color: .morado, indice: -1)
                ForEach(Array(agentes.enumerated()), id: \.offset) { i, a in
                    Divider().overlay(Color.separador)
                    filaMiembro("AC", agentes.count > 1 ? "Agente de código \(i + 1)" : "Agente de código", a, color: .texto3, indice: i)
                }
                if agentes.count < LogicaProyectos.maxAgentes {
                    Divider().overlay(Color.separador)
                    Button("Agregar otro agente de código") {
                        agentes.append(NuevoProyecto.Config(modelo: "sonnet", esfuerzo: "medium"))
                    }
                    .font(.system(size: 15))
                    .foregroundStyle(Color.acento)
                    .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                    .padding(.horizontal, 14)
                }
            }
        }
    }

    private func filaMiembro(_ ini: String, _ rol: String, _ c: NuevoProyecto.Config, color: Color, indice: Int) -> some View {
        Button { editando = indice } label: {
            HStack(spacing: 10) {
                Text(ini).font(.system(size: 12, weight: .semibold)).foregroundStyle(.white)
                    .frame(width: 36, height: 36).background(color, in: Circle())
                VStack(alignment: .leading, spacing: 1) {
                    Text(rol).font(.system(size: 15, weight: .semibold))
                    Text(LogicaProyectos.modeloYEsfuerzo(c.modelo, c.esfuerzo)).font(.system(size: 13)).foregroundStyle(Color.texto2)
                }
                Spacer()
                Image(systemName: "slider.horizontal.3").foregroundStyle(Color.acento).frame(width: 44, height: 44)
            }
            .padding(.horizontal, 14).padding(.vertical, 4)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityHint("Cambiar modelo y esfuerzo")
    }

    private func leerMaquinas() async {
        guard let api = modelo.api else { return }
        do {
            let m = try await api.maquinasEquipo()
            maquinas = m
            if maquina.isEmpty { maquina = m.first { $0.disponible }?.id ?? "" }
        } catch let e as ErrorAPI {
            error = e.mensaje
            maquinas = []
        } catch {}
    }

    private func crear() {
        guard puedeCrear, let api = modelo.api else { return }
        creando = true
        error = nil
        let cuerpo = NuevoProyecto(nombre: nombre.trimmingCharacters(in: .whitespaces), maquina: maquina, cuenta: cuenta,
                                   plantilla: plantilla, orquestador: orquestador,
                                   agentes: Array(agentes.prefix(LogicaProyectos.maxAgentes)), auto_aprobar: autoAprobar)
        Task {
            defer { creando = false }
            do {
                let p = try await api.crearProyecto(cuerpo)
                cerrar()
                creado(p)
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {}
        }
    }
}

/// Modelo y esfuerzo de un miembro del equipo.
struct ElegirModelo: View {
    let titulo: String
    @State var config: NuevoProyecto.Config
    var quitar: (() -> Void)?
    let elegir: (NuevoProyecto.Config) -> Void
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        NavigationStack {
            Form {
                Picker("Modelo", selection: $config.modelo) {
                    ForEach(LogicaProyectos.modelos, id: \.valor) { Text($0.texto).tag($0.valor) }
                }
                Picker("Esfuerzo", selection: $config.esfuerzo) {
                    ForEach(LogicaProyectos.esfuerzos, id: \.valor) { Text($0.texto.prefix(1).uppercased() + $0.texto.dropFirst()).tag($0.valor) }
                }
                if let quitar {
                    Button("Quitar este agente", role: .destructive) {
                        quitar()
                        cerrar()
                    }
                }
            }
            .navigationTitle(titulo)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancelar") { cerrar() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Listo") {
                        elegir(config)
                        cerrar()
                    }
                }
            }
        }
    }
}
