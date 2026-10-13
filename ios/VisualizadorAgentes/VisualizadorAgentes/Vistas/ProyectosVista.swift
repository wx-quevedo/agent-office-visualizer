import SwiftUI

/// Pestaña Proyectos (boceto Main): los proyectos con orquestador y los que solo
/// tienen su PROJECT.md, con su estado y su color, y el botón Nuevo.
struct ProyectosVista: View {
    @Environment(ModeloApp.self) private var modelo
    @State private var nuevo = false

    var body: some View {
        @Bindable var m = modelo
        NavigationStack(path: $m.rutaProyectos) {
            lista
                .navigationTitle("Proyectos")
                .toolbar(.hidden, for: .navigationBar)
                .navigationDestination(for: RutaProyecto.self) { r in
                    ProyectoDetalle(id: r.id, seccionInicial: r.seccion, aviso: r.aviso)
                }
                .navigationDestination(for: String.self) { id in FichaVista(id: id) }
        }
        .sheet(isPresented: $nuevo) {
            NuevoProyectoVista { p in
                modelo.reemplazar(p)
                modelo.abrirProyecto(equipo: p.id)
            }
        }
        .task { await sondear() }
    }

    /// Proyectos con equipo cada 5 s; los del monitor y el consumo cada 30 s.
    private func sondear() async {
        var vuelta = 0
        while !Task.isCancelled {
            await modelo.leerProyectos(todo: vuelta % 6 == 0)
            vuelta += 1
            try? await Task.sleep(for: .seconds(5))
        }
    }

    private var lista: some View {
        let proyectos = modelo.listaProyectos
        return ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Proyectos").font(.system(size: 34, weight: .bold))
                    Spacer()
                    Button { nuevo = true } label: {
                        Label("Nuevo", systemImage: "plus")
                            .font(.system(size: 15, weight: .semibold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 16)
                            .frame(height: 40)
                            .background(Color.acento, in: Capsule())
                    }
                    .buttonStyle(.plain)
                }
                .padding(.top, 8)
                if modelo.proyectosEquipo != nil {
                    Text(LogicaProyectos.resumen(proyectos))
                        .font(.system(size: 15)).foregroundStyle(Color.texto2)
                }
                if let e = modelo.errorProyectos {
                    Text(e).font(.system(size: 14)).foregroundStyle(Color.rojo)
                }
                if modelo.proyectosEquipo == nil && modelo.errorProyectos == nil {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
                }
                ForEach(proyectos) { p in
                    NavigationLink(value: RutaProyecto(id: p.id, seccion: p.conOrquestador ? .chat : .donde)) {
                        FilaProyecto(proyecto: p)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .refreshable { await modelo.leerProyectos() }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
    }
}

struct FilaProyecto: View {
    let proyecto: ProyectoLista

    var body: some View {
        let estado = LogicaProyectos.estado(proyecto)
        let lugar = [Logica.textoCuenta(proyecto.cuenta), Logica.nombreMaquina(proyecto.maquina)].compactMap { $0 }
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(proyecto.nombre).font(.system(size: 17, weight: .semibold)).lineLimit(1)
                Spacer(minLength: 8)
                Text(lugar.joined(separator: " · ")).font(.system(size: 12)).foregroundStyle(Color.texto2)
            }
            Text(LogicaProyectos.dondeVa(proyecto))
                .font(.system(size: 14)).foregroundStyle(Color.texto3).lineLimit(2)
            HStack(spacing: 6) {
                Text(LogicaProyectos.equipoTexto(proyecto))
                    .font(.system(size: 12))
                    .foregroundStyle(Color.texto3)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background(Color.separador, in: RoundedRectangle(cornerRadius: 5))
                Text(estado.texto).font(.system(size: 12, weight: .semibold)).foregroundStyle(estado.tono.color)
                if proyecto.equipo?.esPrueba == true { EtiquetaPrueba() }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(estado.tono.borde))
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Un proyecto

/// Un proyecto con el selector Chat | Equipo | Dónde quedamos (bocetos Chat y Equipo).
/// Sin orquestador solo tiene Dónde quedamos.
struct ProyectoDetalle: View {
    @Environment(ModeloApp.self) private var modelo
    let id: String
    let seccionInicial: SeccionProyecto
    var aviso: String? = nil
    @State private var seccion: SeccionProyecto?

    var body: some View {
        let p = modelo.proyecto(id)
        let actual = p?.conOrquestador == false ? .donde : (seccion ?? seccionInicial)
        VStack(spacing: 0) {
            if let p {
                encabezado(p)
                if p.conOrquestador {
                    Picker("Sección", selection: Binding(get: { actual }, set: { seccion = $0 })) {
                        ForEach(SeccionProyecto.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                }
                switch actual {
                case .chat:
                    if let e = p.equipo { ChatProyecto(proyecto: e, destacar: aviso) }
                case .equipo:
                    if let e = p.equipo { EquipoVista(proyecto: e, agentes: p.agentes) }
                case .donde:
                    DondeDetalle(proyecto: p.donde)
                }
            } else if modelo.proyectosEquipo == nil {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ContentUnavailableView("El proyecto ya no está", systemImage: "folder.badge.questionmark")
            }
        }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.visible, for: .navigationBar)
    }

    private func encabezado(_ p: ProyectoLista) -> some View {
        var detalle: [String] = []
        if let e = p.equipo {
            detalle = [Logica.textoCuenta(e.cuenta), Logica.nombreMaquina(e.maquina),
                       e.equipo.first { $0.rol == "orquestador" }.map { LogicaProyectos.nombreModelo($0.modelo) }].compactMap { $0 }
        } else {
            detalle = [Logica.textoCuenta(p.cuenta), Logica.nombreMaquina(p.maquina), "Sin orquestador"].compactMap { $0 }
        }
        return VStack(alignment: .leading, spacing: 1) {
            Text(p.nombre).font(.system(size: 17, weight: .semibold)).lineLimit(1)
            Text(detalle.joined(separator: " · ")).font(.system(size: 12)).foregroundStyle(Color.texto2).lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16)
    }
}

// MARK: - Chat

/// Chat con el orquestador (boceto Chat): burbujas con markdown, tarjetas de
/// orden, campo de texto, dictado y enviar. Se lee cada 2 s.
struct ChatProyecto: View {
    @Environment(ModeloApp.self) private var modelo
    let proyecto: ProyectoEquipo
    /// Clave del aviso que se responde: el mensaje o la orden quedan a la vista.
    var destacar: String? = nil
    @State private var chat: ChatRespuesta?
    @State private var yaDestacado = false
    @State private var locales: [String: Orden] = [:]
    @State private var enviados: [MensajeChat] = []
    @State private var texto = ""
    @State private var enviando = false
    @State private var error: String?
    @State private var dictado = Dictado()
    @State private var antesDeDictar = ""
    @FocusState private var escribiendo: Bool

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { lector in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        if let nota = LogicaProyectos.notaChat(proyecto.estado) {
                            Text(nota).font(.system(size: 13)).foregroundStyle(Color.naranja)
                                .frame(maxWidth: .infinity, alignment: .center).multilineTextAlignment(.center)
                        }
                        if let items {
                            if items.isEmpty {
                                Text("Todavía no hay mensajes. Escríbele al orquestador para empezar.")
                                    .font(.system(size: 14)).foregroundStyle(Color.texto2)
                                    .frame(maxWidth: .infinity).padding(.top, 24)
                            }
                            ForEach(items) { item in fila(item).id(item.id) }
                                .onAppear { mostrarAviso(lector) }
                        } else {
                            ProgressView().frame(maxWidth: .infinity).padding(.top, 40)
                        }
                        Color.clear.frame(height: 1).id("fin")
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                }
                .scrollDismissesKeyboard(.interactively)
                .defaultScrollAnchor(.bottom)
                .onChange(of: items?.count) {
                    if yaDestacado || destacar == nil { lector.scrollTo("fin", anchor: .bottom) } else { mostrarAviso(lector) }
                }
            }
            barra
        }
        .task(id: proyecto.id) { await sondear() }
        .onChange(of: dictado.texto) { _, nuevo in
            guard !nuevo.isEmpty else { return }
            texto = antesDeDictar.isEmpty ? nuevo : antesDeDictar + " " + nuevo
        }
        .onDisappear { dictado.detener() }
    }

    private var items: [LogicaProyectos.ItemChat]? {
        guard let chat else { return nil }
        let ids = Set(chat.mensajes.map(\.id))
        let mensajes = chat.mensajes + enviados.filter { !ids.contains($0.id) }
        let ordenes = chat.ordenes.map { o in
            if let l = locales[o.id], (FechaISO.leer(l.actualizado) ?? .distantPast) >= (FechaISO.leer(o.actualizado) ?? .distantPast) { return l }
            return o
        }
        return LogicaProyectos.mezclar(mensajes, ordenes)
    }

    /// Responder: lleva a la pregunta (o la orden) y deja el campo listo para escribir.
    private func mostrarAviso(_ lector: ScrollViewProxy) {
        guard !yaDestacado, let objetivo = LogicaAvisos.itemChat(destacar),
              items?.contains(where: { $0.id == objetivo }) == true else { return }
        yaDestacado = true
        DispatchQueue.main.async {
            withAnimation { lector.scrollTo(objetivo, anchor: .center) }
            if objetivo.hasPrefix("m-") { escribiendo = true }
        }
    }

    @ViewBuilder
    private func fila(_ item: LogicaProyectos.ItemChat) -> some View {
        let resaltada = LogicaAvisos.itemChat(destacar) == item.id
        switch item {
        case .mensaje(let m):
            let mio = m.autor == "washington"
            VStack(alignment: mio ? .trailing : .leading, spacing: 2) {
                TextoMarkdown(texto: m.texto, tamano: 15, color: mio ? .white : .texto)
                    .padding(.horizontal, 12).padding(.vertical, 10)
                    .background(mio ? Color.acento : Color.white,
                                in: UnevenRoundedRectangle(topLeadingRadius: 16, bottomLeadingRadius: mio ? 16 : 4,
                                                           bottomTrailingRadius: mio ? 4 : 16, topTrailingRadius: 16))
                    .overlay(UnevenRoundedRectangle(topLeadingRadius: 16, bottomLeadingRadius: mio ? 16 : 4,
                                                    bottomTrailingRadius: mio ? 4 : 16, topTrailingRadius: 16)
                        .strokeBorder(mio ? Color.clear : (resaltada ? Color.morado : Color.borde), lineWidth: resaltada ? 2 : 1))
                Text(Logica.horaMinuto(m.creado)).font(.system(size: 11)).foregroundStyle(Color.texto2)
            }
            .frame(maxWidth: 330, alignment: mio ? .trailing : .leading)
            .frame(maxWidth: .infinity, alignment: mio ? .trailing : .leading)
        case .orden(let o):
            TarjetaOrden(orden: o, resaltada: resaltada) { nueva in locales[nueva.id] = nueva }
        }
    }

    private var barra: some View {
        VStack(spacing: 4) {
            if let e = dictado.error ?? error {
                Text(e).font(.system(size: 12)).foregroundStyle(Color.rojo).frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack(alignment: .bottom, spacing: 8) {
                TextField("Escríbele al orquestador", text: $texto, axis: .vertical)
                    .lineLimit(1...5)
                    .font(.system(size: 15))
                    .focused($escribiendo)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Color.white, in: RoundedRectangle(cornerRadius: 20))
                    .overlay(RoundedRectangle(cornerRadius: 20).strokeBorder(Color.bordeCampo))
                    .accessibilityLabel("Mensaje para el orquestador")
                Button {
                    if !dictado.escuchando { antesDeDictar = texto.trimmingCharacters(in: .whitespacesAndNewlines) }
                    escribiendo = false
                    Task { await dictado.alternar() }
                } label: {
                    Image(systemName: dictado.escuchando ? "stop.fill" : "mic")
                        .font(.system(size: 17, weight: .medium))
                        .foregroundStyle(dictado.escuchando ? Color.white : Color.texto)
                        .frame(width: 44, height: 44)
                        .background(dictado.escuchando ? Color.rojo : Color.white, in: Circle())
                        .overlay(Circle().strokeBorder(dictado.escuchando ? Color.clear : Color.bordeCampo))
                }
                .buttonStyle(.plain)
                .accessibilityLabel(dictado.escuchando ? "Detener el dictado" : "Dictar")
                Button(action: enviar) {
                    Group {
                        if enviando { ProgressView().tint(.white) } else { Image(systemName: "arrow.up").font(.system(size: 17, weight: .bold)) }
                    }
                    .foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(Color.acento, in: Circle())
                }
                .buttonStyle(.plain)
                .disabled(enviando || texto.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .opacity(texto.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? 0.5 : 1)
                .accessibilityLabel("Enviar")
            }
        }
        .padding(.horizontal, 12)
        .padding(.top, 8)
        .padding(.bottom, 8)
        .background(Color.fondo)
        .overlay(alignment: .top) { Divider().overlay(Color.borde) }
    }

    private func sondear() async {
        while !Task.isCancelled {
            await leer()
            try? await Task.sleep(for: .seconds(2))
        }
    }

    private func leer() async {
        guard let api = modelo.api else { return }
        do {
            chat = try await api.chat(proyecto.id)
            error = nil
        } catch ErrorAPI.sinSesion {
            modelo.sesionVencida()
        } catch let e as ErrorAPI {
            if chat == nil { error = e.mensaje }
        } catch {}
    }

    private func enviar() {
        let t = texto.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty, let api = modelo.api else { return }
        dictado.detener()
        enviando = true
        error = nil
        Task {
            defer { enviando = false }
            do {
                let m = try await api.escribir(proyecto.id, texto: String(t.prefix(8000)))
                enviados.append(m)
                texto = ""
                await leer()
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {}
        }
    }
}

// MARK: - Equipo

/// Equipo del proyecto (boceto Equipo): miembros, órdenes, aprobar órdenes
/// automáticamente, Pausar o Reanudar el equipo y Reglas de la casa.
struct EquipoVista: View {
    @Environment(ModeloApp.self) private var modelo
    let proyecto: ProyectoEquipo
    let agentes: [Agente]
    @State private var ordenes: [Orden]?
    @State private var ocupado = false
    @State private var error: String?
    @State private var confirmarAuto = false
    @State private var agregar = false
    @State private var reglas = false
    @State private var confirmarDetener = false

    var body: some View {
        let nAgentes = proyecto.equipo.filter { $0.rol == "agente" }.count
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                if let r = proyecto.ruta {
                    Text(r).font(.mono(12)).foregroundStyle(Color.texto2).lineLimit(1).truncationMode(.middle)
                }
                ForEach(proyecto.equipo) { m in miembro(m, agentes: nAgentes) }
                if nAgentes < LogicaProyectos.maxAgentes {
                    Button { agregar = true } label: {
                        Text("Agregar agente de código")
                            .font(.system(size: 15)).foregroundStyle(Color.acento)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.grisBoton, style: StrokeStyle(lineWidth: 1, dash: [4])))
                    }
                    .buttonStyle(.plain)
                    .disabled(ocupado)
                }
                ordenesTarjeta
                Tarjeta {
                    Toggle(isOn: Binding(get: { proyecto.auto_aprobar }, set: { nuevo in
                        if nuevo { confirmarAuto = true } else { cambiarAuto(false) }
                    })) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Aprobar órdenes automáticamente").font(.system(size: 15))
                            Text(proyecto.auto_aprobar
                                 ? "Encendido: las órdenes del orquestador llegan al agente sin pasar por ti."
                                 : "Apagado: apruebas cada orden del orquestador al agente.")
                                .font(.system(size: 12)).foregroundStyle(Color.texto2)
                        }
                    }
                    .tint(.verde)
                    .disabled(ocupado)
                    .padding(.horizontal, 14).padding(.vertical, 12)
                }
                Tarjeta {
                    Toggle(isOn: Binding(get: { proyecto.esPrueba }, set: { nuevo in
                        accion { api in try await api.marcarPrueba(proyecto.id, prueba: nuevo) }
                    })) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Proyecto de prueba").font(.system(size: 15))
                            Text("Sin avisos ni Decisiones; se detiene solo tras 30 min sin actividad.")
                                .font(.system(size: 12)).foregroundStyle(Color.texto2)
                        }
                    }
                    .tint(.verde)
                    .disabled(ocupado)
                    .padding(.horizontal, 14).padding(.vertical, 12)
                }
                if let error { Text(error).font(.system(size: 13)).foregroundStyle(Color.rojo) }
                HStack(spacing: 8) {
                    botonPausa
                    Button { reglas = true } label: {
                        Text("Reglas de la casa").font(.system(size: 15, weight: .medium))
                            .frame(maxWidth: .infinity, minHeight: 46)
                            .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.bordeCampo))
                    }
                    .buttonStyle(.plain)
                }
                .padding(.top, 2)
                if ["activo", "pausado", "error"].contains(proyecto.estado) {
                    Button(role: .destructive) { confirmarDetener = true } label: {
                        Text("Detener el equipo").font(.system(size: 15, weight: .medium)).foregroundStyle(Color.rojo)
                            .frame(maxWidth: .infinity, minHeight: 46)
                            .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.bordeRojo))
                    }
                    .buttonStyle(.plain)
                    .disabled(ocupado)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 4)
            .padding(.bottom, 24)
        }
        .refreshable { await leerOrdenes() }
        .task(id: proyecto.id) {
            while !Task.isCancelled {
                await leerOrdenes()
                try? await Task.sleep(for: .seconds(5))
            }
        }
        .alert("Aprobar órdenes automáticamente", isPresented: $confirmarAuto) {
            Button("Encender", role: .destructive) { cambiarAuto(true) }
            Button("Cancelar", role: .cancel) {}
        } message: {
            Text("Las órdenes del orquestador llegarán a los agentes sin pasar por ti. Los permisos peligrosos siguen pidiendo tu aprobación.")
        }
        .alert("Detener el equipo", isPresented: $confirmarDetener) {
            Button("Detener", role: .destructive) {
                accion { api in try await api.accionEquipo(proyecto.id, "detener") }
            }
            Button("Cancelar", role: .cancel) {}
        } message: {
            Text("Se cierran el orquestador y los agentes de \(proyecto.nombre). Se puede reanudar después.")
        }
        .sheet(isPresented: $agregar) {
            AgregarAgente { modelo, esfuerzo in
                accion { api in try await api.agregarAgente(proyecto.id, modelo: modelo, esfuerzo: esfuerzo) }
            }
            .presentationDetents([.medium])
        }
        .navigationDestination(isPresented: $reglas) { ReglasVista(proyecto: proyecto) }
    }

    private func miembro(_ m: ProyectoEquipo.Miembro, agentes n: Int) -> some View {
        let orq = m.rol == "orquestador"
        let espera = orq && (proyecto.ordenes_por_aprobar ?? 0) > 0
        let estado = espera ? "Espera que apruebes una orden"
            : (m.oficina.map { $0.espera ?? $0.nombre } ?? LogicaProyectos.estadoMiembro(m.estado))
        let sesion = m.session_id.flatMap { s in agentes.first { $0.id == s } }
        return HStack(spacing: 12) {
            Text(LogicaProyectos.iniciales(m))
                .font(.system(size: 14, weight: .semibold)).foregroundStyle(.white)
                .frame(width: 44, height: 44)
                .background(orq ? Color.morado : Color.texto3, in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(LogicaProyectos.nombreRol(m, agentes: n)).font(.system(size: 16, weight: .semibold))
                Text(LogicaProyectos.modeloYEsfuerzo(m.modelo, m.esfuerzo)).font(.system(size: 13)).foregroundStyle(Color.texto2)
                Text(estado).font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(espera ? Color.morado : (m.estado == "error" ? Color.rojo : Color.texto2))
                    .lineLimit(2)
            }
            Spacer(minLength: 4)
            if let s = sesion {
                NavigationLink(value: s.id) {
                    Image(systemName: "chevron.right").font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Color.bordeCampo).frame(width: 44, height: 44)
                }
                .accessibilityLabel("Abrir ficha")
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background(Color.white, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(espera ? Color.bordeMorado : Color.borde))
    }

    private var ordenesTarjeta: some View {
        Tarjeta {
            VStack(alignment: .leading, spacing: 0) {
                Rotulo(texto: "Órdenes del orquestador")
                    .padding(.horizontal, 14).padding(.top, 12).padding(.bottom, 4)
                if let ordenes {
                    if ordenes.isEmpty {
                        Text("Todavía no hay órdenes.").font(.system(size: 14)).foregroundStyle(Color.texto2)
                            .padding(.horizontal, 14).padding(.vertical, 10)
                    }
                    ForEach(ordenes.prefix(15)) { o in
                        let e = LogicaProyectos.estadoOrden(o.estado)
                        Divider().overlay(Color.separador)
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Text(Logica.horaMinuto(o.creado)).font(.mono(12)).foregroundStyle(Color.texto2).frame(width: 42, alignment: .leading)
                            Text(Logica.recortar(MarkdownLigero.sinHTML(LogicaProyectos.tituloCorto(o)), 90)).font(.system(size: 14)).lineLimit(2)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Text(e.texto.prefix(1).uppercased() + e.texto.dropFirst())
                                .font(.system(size: 12, weight: .semibold)).foregroundStyle(e.tono.color)
                        }
                        .padding(.horizontal, 14).padding(.vertical, 10)
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.vertical, 12)
                }
            }
            .padding(.bottom, 4)
        }
    }

    @ViewBuilder
    private var botonPausa: some View {
        let pausable = proyecto.estado == "activo" || proyecto.estado == "error"
        let reanudable = proyecto.estado == "pausado" || proyecto.estado == "detenido"
        Button {
            accion { api in try await api.accionEquipo(proyecto.id, pausable ? "pausar" : "reanudar") }
        } label: {
            Text(pausable ? "Pausar el equipo" : reanudable ? "Reanudar el equipo" : (LogicaProyectos.estadosDetenidos[proyecto.estado] ?? "Esperando…"))
                .font(.system(size: 15, weight: .medium))
                .frame(maxWidth: .infinity, minHeight: 46)
                .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.bordeCampo))
        }
        .buttonStyle(.plain)
        .disabled(ocupado || !(pausable || reanudable))
    }

    private func leerOrdenes() async {
        guard let api = modelo.api else { return }
        if let o = try? await api.ordenes(proyecto.id) {
            ordenes = o.sorted { (FechaISO.leer($0.creado) ?? .distantPast) > (FechaISO.leer($1.creado) ?? .distantPast) }
        }
    }

    private func cambiarAuto(_ activo: Bool) {
        accion { api in try await api.autoAprobar(proyecto.id, activo: activo) }
    }

    private func accion(_ paso: @escaping (ClienteAPI) async throws -> ProyectoEquipo) {
        guard let api = modelo.api else { return }
        ocupado = true
        error = nil
        Task {
            defer { ocupado = false }
            do {
                modelo.reemplazar(try await paso(api))
            } catch ErrorAPI.sinSesion {
                modelo.sesionVencida()
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {}
        }
    }
}

/// Modelo y esfuerzo de un agente de código nuevo.
struct AgregarAgente: View {
    let agregar: (String, String) -> Void
    @State private var modelo = "sonnet"
    @State private var esfuerzo = "medium"
    @Environment(\.dismiss) private var cerrar

    var body: some View {
        NavigationStack {
            Form {
                Picker("Modelo", selection: $modelo) {
                    ForEach(LogicaProyectos.modelos, id: \.valor) { Text($0.texto).tag($0.valor) }
                }
                Picker("Esfuerzo", selection: $esfuerzo) {
                    ForEach(LogicaProyectos.esfuerzos, id: \.valor) { Text($0.texto.prefix(1).uppercased() + $0.texto.dropFirst()).tag($0.valor) }
                }
            }
            .navigationTitle("Agente de código")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancelar") { cerrar() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Agregar") {
                        agregar(modelo, esfuerzo)
                        cerrar()
                    }
                }
            }
        }
    }
}

/// Etiqueta "Prueba" de los proyectos de prueba.
struct EtiquetaPrueba: View {
    var body: some View {
        Text("Prueba")
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(Color.texto2)
            .padding(.horizontal, 6).padding(.vertical, 2)
            .overlay(RoundedRectangle(cornerRadius: 4).strokeBorder(Color.bordeCampo))
    }
}
