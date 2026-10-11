import SwiftUI

/// Bandeja de Ideas (boceto Ideas): anotarla ahora (escrita o dictada), asignarla después.
struct IdeasVista: View {
    @Environment(ModeloApp.self) private var modelo
    @State private var texto = ""
    @State private var proyecto: String?
    @State private var dictada = false
    @State private var ideas: [Idea]?
    @State private var proyectos: [String] = []
    @State private var guardando = false
    @State private var error: String?
    @State private var cambiando: Idea?
    @State private var dictado = Dictado()
    @State private var antesDeDictar = ""
    @FocusState private var escribiendo: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Ideas").font(.system(size: 34, weight: .bold))
                Text("Anótala ahora, asígnala después.")
                    .font(.system(size: 15)).foregroundStyle(Color.texto2)
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            // Fuera de la lista: dentro de una fila, la lista se queda con los toques del selector.
            nueva
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 6)
            guardadasLista
        }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Listo") { escribiendo = false }
            }
        }
        .task { await leer() }
        .onChange(of: dictado.texto) { _, nuevo in
            guard !nuevo.isEmpty else { return }
            // Lo dictado se suma a lo que ya estaba escrito.
            texto = antesDeDictar.isEmpty ? nuevo : antesDeDictar + " " + nuevo
            dictada = true
        }
        .onDisappear { dictado.detener() }
        .sheet(item: $cambiando) { i in
            SelectorProyecto(actual: i.proyecto, proyectos: proyectos) { nuevo in
                cambiarProyecto(i, nuevo)
            }
            .presentationDetents([.medium, .large])
        }
    }

    private var guardadasLista: some View {
        List {
            Section {
                if let ideas {
                    let lista = LogicaBandejas.guardadas(ideas)
                    if lista.isEmpty {
                        Text("Todavía no hay ideas guardadas.")
                            .font(.system(size: 15)).foregroundStyle(Color.texto2)
                            .listRowBackground(Color.clear)
                    }
                    ForEach(lista) { i in
                        fila(i)
                            .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                            .listRowBackground(Color.clear)
                            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                Button("Archivar", systemImage: "archivebox") { archivar(i) }
                                    .tint(.texto3)
                            }
                            .swipeActions(edge: .leading) {
                                Button("Proyecto", systemImage: "folder") { cambiando = i }
                                    .tint(.acento)
                            }
                            .contextMenu {
                                Button("Cambiar el proyecto", systemImage: "folder") { cambiando = i }
                                Button("Archivar", systemImage: "archivebox") { archivar(i) }
                            }
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity).listRowBackground(Color.clear)
                }
            } header: {
                Rotulo(texto: "Guardadas · \(ideas.map { LogicaBandejas.guardadas($0).count } ?? 0)")
                    .textCase(nil)
            } footer: {
                if ideas?.isEmpty == false {
                    Text("Desliza a la izquierda para archivar y a la derecha para cambiar el proyecto.")
                        .font(.system(size: 12)).foregroundStyle(Color.texto2)
                }
            }
            .listRowSeparator(.hidden)
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .scrollDismissesKeyboard(.immediately)
        .refreshable { await leer() }
    }

    // MARK: - Nueva idea

    private var nueva: some View {
        VStack(alignment: .leading, spacing: 10) {
            Rotulo(texto: "Nueva idea")
            ZStack(alignment: .topLeading) {
                if texto.isEmpty && !dictado.escuchando {
                    Text("Escríbela o díctala").font(.system(size: 16)).foregroundStyle(Color.texto2.opacity(0.7))
                        .padding(.top, 8).padding(.leading, 5)
                        .allowsHitTesting(false)
                }
                TextEditor(text: $texto)
                    .font(.system(size: 16))
                    .scrollContentBackground(.hidden)
                    .frame(height: 84)
                    .focused($escribiendo)
                    .accessibilityLabel("Nueva idea")
                    .onChange(of: texto) { _, t in if t.isEmpty { dictada = false } }
            }
            if dictado.escuchando {
                Label(dictado.enDispositivo ? "Escuchando (en el iPhone)…" : "Escuchando…", systemImage: "waveform")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(Color.acento)
                    .symbolEffect(.variableColor.iterative)
            }
            if let e = dictado.error ?? error {
                Text(e).font(.system(size: 13)).foregroundStyle(Color.rojo)
            }
            HStack(spacing: 8) {
                Button {
                    escribiendo = false
                    if !dictado.escuchando {
                        antesDeDictar = texto.trimmingCharacters(in: .whitespacesAndNewlines)
                    }
                    Task { await dictado.alternar() }
                } label: {
                    Image(systemName: dictado.escuchando ? "stop.fill" : "mic.fill")
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(width: 50, height: 50)
                        .background(dictado.escuchando ? Color.rojo : Color.acento, in: Circle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(dictado.escuchando ? "Detener el dictado" : "Dictar")

                Menu {
                    Picker("Proyecto", selection: $proyecto) {
                        ForEach(proyectos, id: \.self) { Text($0).tag(Optional($0)) }
                        Text(LogicaBandejas.sinProyecto).tag(String?.none)
                    }
                } label: {
                    HStack {
                        Text(proyecto ?? LogicaBandejas.sinProyecto).lineLimit(1)
                        Spacer(minLength: 4)
                        Image(systemName: "chevron.up.chevron.down").font(.system(size: 12))
                    }
                    .font(.system(size: 15))
                    .foregroundStyle(Color.texto)
                    .padding(.horizontal, 10)
                    .frame(maxWidth: .infinity, minHeight: 44)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.bordeCampo))
                }
                .accessibilityLabel("Proyecto: \(proyecto ?? LogicaBandejas.sinProyecto)")

                Button(action: guardar) {
                    Group {
                        if guardando { ProgressView().tint(.white) } else { Text("Guardar") }
                    }
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 16)
                    .frame(minHeight: 44)
                    .background(Color.texto3, in: RoundedRectangle(cornerRadius: 10))
                }
                .buttonStyle(.plain)
                .disabled(guardando || LogicaBandejas.textoIdea(texto) == nil)
                .opacity(LogicaBandejas.textoIdea(texto) == nil ? 0.5 : 1)
            }
        }
        .padding(14)
        .background(Color.white, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Color.bordeCampo))
    }

    // MARK: - Guardadas

    private func fila(_ i: Idea) -> some View {
        let e = LogicaBandejas.estado(i)
        return VStack(alignment: .leading, spacing: 6) {
            Text(i.texto).font(.system(size: 15)).fixedSize(horizontal: false, vertical: true)
            HStack {
                Text(i.proyecto ?? "Sin proyecto")
                    .font(.system(size: 12))
                    .foregroundStyle(Color.texto3)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Color.separador, in: RoundedRectangle(cornerRadius: 5))
                if i.origen == "dictada" {
                    Image(systemName: "mic").font(.system(size: 11)).foregroundStyle(Color.texto2)
                        .accessibilityLabel("Dictada")
                }
                Spacer()
                Text(e.texto).font(.system(size: 12, weight: .semibold)).foregroundStyle(e.tono.color)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Acciones

    private func leer() async {
        guard let api = modelo.api else { return }
        do {
            let r = try await api.ideas()
            ideas = r.ideas
            proyectos = LogicaBandejas.proyectos(r.proyectos)
            error = nil
        } catch ErrorAPI.sinSesion {
            modelo.sesionVencida()
        } catch let e as ErrorAPI {
            error = e.mensaje
        } catch {}
    }

    private func guardar() {
        guard let t = LogicaBandejas.textoIdea(texto), let api = modelo.api else { return }
        dictado.detener()
        guardando = true
        error = nil
        Task {
            defer { guardando = false }
            do {
                _ = try await api.crearIdea(texto: t, proyecto: proyecto, dictada: dictada)
                texto = ""
                dictada = false
                escribiendo = false
                await leer()
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {}
        }
    }

    private func archivar(_ i: Idea) {
        Task {
            do {
                _ = try await modelo.api?.archivar(idea: i.id)
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {}
            await leer()
        }
    }

    private func cambiarProyecto(_ i: Idea, _ nuevo: String?) {
        Task {
            do {
                _ = try await modelo.api?.cambiarProyecto(idea: i.id, proyecto: nuevo)
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {}
            await leer()
        }
    }
}

/// Hoja para elegir el proyecto de una idea guardada.
struct SelectorProyecto: View {
    let actual: String?
    let proyectos: [String]
    let elegir: (String?) -> Void
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        NavigationStack {
            List {
                ForEach(proyectos, id: \.self) { p in fila(p, valor: p) }
                fila(LogicaBandejas.sinProyecto, valor: nil)
            }
            .navigationTitle("Proyecto de la idea")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { Button("Cancelar") { cerrar() } }
        }
    }

    private func fila(_ titulo: String, valor: String?) -> some View {
        Button {
            if valor != actual { elegir(valor) }
            cerrar()
        } label: {
            HStack {
                Text(titulo).foregroundStyle(Color.texto)
                Spacer()
                if valor == actual { Image(systemName: "checkmark").foregroundStyle(Color.acento) }
            }
        }
    }
}
