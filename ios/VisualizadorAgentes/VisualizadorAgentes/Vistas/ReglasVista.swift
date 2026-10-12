import SwiftUI

/// Reglas de la casa de un proyecto (boceto Reglas): un interruptor por regla para
/// este proyecto y Agregar (una regla nueva para todos los proyectos).
struct ReglasVista: View {
    @Environment(ModeloApp.self) private var modelo
    let proyecto: ProyectoEquipo
    @State private var datos: ReglasDeProyecto?
    @State private var error: String?
    @State private var cambiando: String?
    @State private var agregar = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("Todos los orquestadores las heredan al crear un proyecto. Puedes apagar una solo para \(proyecto.nombre).")
                    .font(.system(size: 14)).foregroundStyle(Color.texto2)
                if let error { Text(error).font(.system(size: 13)).foregroundStyle(Color.rojo) }
                if let reglas = datos?.reglas {
                    Tarjeta {
                        VStack(spacing: 0) {
                            ForEach(Array(reglas.enumerated()), id: \.element.id) { i, r in
                                if i > 0 { Divider().overlay(Color.separador) }
                                Toggle(isOn: Binding(get: { r.activa }, set: { ajustar(r, $0) })) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(r.texto).font(.system(size: 15)).fixedSize(horizontal: false, vertical: true)
                                        Text(LogicaProyectos.nombreTipo(r.tipo) + (r.ajustada == true ? " · cambiada en este proyecto" : ""))
                                            .font(.system(size: 12)).foregroundStyle(Color.texto2)
                                    }
                                }
                                .tint(.verde)
                                .disabled(cambiando == r.id)
                                .padding(.horizontal, 14).padding(.vertical, 10)
                                .accessibilityHint("Aplicar en este proyecto")
                            }
                        }
                    }
                } else if error == nil {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
                }
                Text("Los cambios se editan también desde la web, en Ajustes.")
                    .font(.system(size: 13)).foregroundStyle(Color.texto2)
                    .frame(maxWidth: .infinity).multilineTextAlignment(.center).padding(.top, 6)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .refreshable { await leer() }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
        .navigationTitle("Reglas de la casa")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { Button("Agregar") { agregar = true } }
        .task { await leer() }
        .sheet(isPresented: $agregar) {
            NuevaRegla { texto, tipo, activa in crear(texto, tipo, activa) }
                .presentationDetents([.medium, .large])
        }
    }

    private func leer() async {
        guard let api = modelo.api else { return }
        do {
            datos = try await api.reglasDe(proyecto.id)
            error = nil
        } catch ErrorAPI.sinSesion {
            modelo.sesionVencida()
        } catch let e as ErrorAPI {
            error = e.mensaje
        } catch {}
    }

    private func ajustar(_ r: ReglaProyecto, _ activa: Bool) {
        guard let api = modelo.api else { return }
        cambiando = r.id
        // Se ve al instante; si el servidor falla, se vuelve a leer.
        if let i = datos?.reglas.firstIndex(where: { $0.id == r.id }) { datos?.reglas[i].activa = activa }
        Task {
            defer { cambiando = nil }
            do {
                datos = try await api.ajustarRegla(proyecto: proyecto.id, regla: r.id, activa: activa)
                error = nil
            } catch let e as ErrorAPI {
                error = e.mensaje
                await leer()
            } catch {}
        }
    }

    private func crear(_ texto: String, _ tipo: String, _ activa: Bool) {
        guard let api = modelo.api else { return }
        Task {
            do {
                _ = try await api.crearRegla(texto: texto, tipo: tipo, activaPorDefecto: activa)
                await leer()
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {}
        }
    }
}

/// Una regla nueva de la casa (POST /reglas: vale para todos los proyectos).
struct NuevaRegla: View {
    let crear: (String, String, Bool) -> Void
    @State private var texto = ""
    @State private var tipo = "otra"
    @State private var activa = true
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Texto de la regla", text: $texto, axis: .vertical).lineLimit(2...5)
                } footer: {
                    Text("La heredan todos los orquestadores; en cada proyecto se puede apagar.")
                }
                Picker("Tipo", selection: $tipo) {
                    ForEach(LogicaProyectos.tiposRegla, id: \.valor) { Text($0.texto).tag($0.valor) }
                }
                Toggle("Encendida por defecto", isOn: $activa).tint(.verde)
            }
            .navigationTitle("Nueva regla")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancelar") { cerrar() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Agregar") {
                        crear(String(texto.trimmingCharacters(in: .whitespacesAndNewlines).prefix(500)), tipo, activa)
                        cerrar()
                    }
                    .disabled(texto.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }
}
