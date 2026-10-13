import Foundation
import Observation
import UIKit

enum Pestana: Hashable { case oficina, proyectos, decisiones, ideas }

/// Estado de la app: sesión, bloqueo y datos en vivo de la oficina.
@MainActor
@Observable
final class ModeloApp {
    // Sesión
    private(set) var credencial: Credencial?
    var bloqueada = false
    var usarFaceID: Bool {
        didSet { UserDefaults.standard.set(usarFaceID, forKey: "usarFaceID") }
    }

    // Navegación
    var pestana: Pestana = .oficina
    var rutaOficina: [String] = []
    var rutaProyectos: [RutaProyecto] = []

    // Proyectos (etapa 4): con equipo, los del monitor (Dónde quedamos) y el consumo de hoy.
    private(set) var proyectosEquipo: [ProyectoEquipo]?
    private(set) var proyectosMonitor: [ProyectoApi]?
    private(set) var consumo: Consumo?
    private(set) var errorProyectos: String?

    // Avisos de los orquestadores (Prompt 43): los que se pueden atender y el que se
    // anuncia ahora (cada clave una sola vez).
    private(set) var avisos: [AvisoOrquestador] = []
    /// El proyecto cuyo chat está a la vista: sus avisos no se notifican.
    var chatAbierto: String?
    @ObservationIgnored private var ultimaLecturaAvisos: Date = .distantPast
    @ObservationIgnored private var avisosLeidos = false

    // Datos en vivo
    private(set) var estado: EstadoOficina?
    private(set) var sinConexion = false
    private(set) var ahora = Date()
    private(set) var configPermisos: ConfigPermisos?

    private var sondeo: Task<Void, Never>?
    private let cliente = UUID().uuidString
    @ObservationIgnored private var ultimoLatido: Date = .distantPast

    static let refresco: TimeInterval = 2
    static let latido: TimeInterval = 30

    init(credencial: Credencial? = Llavero.leer()) {
        self.credencial = credencial
        self.usarFaceID = UserDefaults.standard.bool(forKey: "usarFaceID")
        self.bloqueada = credencial != nil && usarFaceID
    }

    var api: ClienteAPI? { credencial.map { ClienteAPI(credencial: $0) } }

    var agentes: [Agente] { estado?.agentes ?? [] }

    var visibles: [Agente] { Logica.filtrar(agentes, cuenta: .todas, ahora: ahora) }

    /// Insignia de Decisiones: lo que tiene una acción posible (la bandeja del servidor,
    /// que ya cuenta las órdenes, más las preguntas de los orquestadores).
    var pendientes: Int {
        LogicaAvisos.insignia(pendientes: estado?.decisiones_pendientes ?? Logica.pendientes(visibles), avisos: avisos)
    }

    func agente(_ id: String) -> Agente? { agentes.first { $0.id == id } }

    // MARK: - Entrar y salir

    func entrar(servidor: URL, contrasena: String, faceID: Bool) async throws {
        let api = ClienteAPI(servidor: servidor)
        let c = try await api.entrar(contrasena: contrasena, dispositivo: "\(UIDevice.current.name) · app iOS")
        guard Llavero.guardar(c) else {
            throw ErrorAPI.servidor(codigo: 0, mensaje: "No se pudo guardar la sesión en el Llavero.")
        }
        usarFaceID = faceID
        credencial = c
        bloqueada = false
        estado = nil
        iniciar()
    }

    func salir() {
        let api = self.api
        Task { await api?.salir() }
        cerrarSesionLocal()
    }

    /// La sesión venció o la cerraron desde la web: de vuelta a Entrar.
    func sesionVencida() {
        cerrarSesionLocal()
    }

    private func cerrarSesionLocal() {
        detener()
        Llavero.borrar()
        credencial = nil
        estado = nil
        rutaOficina = []
        rutaProyectos = []
        avisos = []
        avisosLeidos = false
        proyectosEquipo = nil
        proyectosMonitor = nil
        bloqueada = false
        OficinaWeb.olvidar()
    }

    // MARK: - Bloqueo con Face ID

    func alPasarAFondo() {
        detener()
        if credencial != nil && usarFaceID { bloqueada = true }
    }

    func desbloquear() async {
        switch await Autenticacion.comprobar(motivo: "Abrir la oficina de agentes") {
        case .ok, .sinBloqueo: bloqueada = false
        case .cancelado: break
        }
    }

    // MARK: - Lectura en vivo (GET /agents/state cada 2 s, como la web)

    func iniciar() {
        guard sondeo == nil, credencial != nil else { return }
        sondeo = Task { [weak self] in
            var fallos = 0
            while !Task.isCancelled {
                guard let self else { return }
                let ok = await self.leerUnaVez()
                fallos = ok ? 0 : fallos + 1
                // Si se corta, reintenta solo, cada vez un poco más espaciado (hasta 15 s).
                let espera = ok ? Self.refresco : min(15, Self.refresco * pow(2, Double(min(fallos, 3))))
                try? await Task.sleep(for: .seconds(espera))
            }
        }
    }

    func detener() {
        sondeo?.cancel()
        sondeo = nil
    }

    /// Una lectura: estado, latido de presencia cada 30 s y la lista de comandos peligrosos.
    @discardableResult
    func leerUnaVez() async -> Bool {
        guard let api else { return false }
        do {
            let e = try await api.estado()
            estado = e
            sinConexion = false
            ahora = Date()
            if Date().timeIntervalSince(ultimoLatido) >= Self.latido {
                ultimoLatido = Date()
                try? await api.presencia(cliente: cliente)
            }
            if configPermisos == nil { configPermisos = try? await api.configPermisos() }
            if Date().timeIntervalSince(ultimaLecturaAvisos) >= 5 { await leerAvisos() }
            return true
        } catch ErrorAPI.sinSesion {
            sesionVencida()
            return false
        } catch {
            sinConexion = true
            ahora = Date()
            return false
        }
    }

    // MARK: - Permisos

    func esPeligroso(_ p: Permiso) -> Bool { esPeligroso(herramienta: p.herramienta, detalle: p.detalle) }

    func esPeligroso(herramienta: String, detalle: String) -> Bool {
        let lista = configPermisos?.confirmar ?? ModeloApp.confirmarPorDefecto
        return Logica.pideConfirmacion(herramienta: herramienta, detalle: detalle, lista: lista)
    }

    func decidir(_ p: Permiso, aprobar: Bool, motivo: String? = nil) async throws {
        try await decidir(id: p.id, herramienta: p.herramienta, detalle: p.detalle, aprobar: aprobar, motivo: motivo)
    }

    /// Aprobar un comando peligroso pide Face ID antes de llamar al servidor.
    /// Devuelve false si se canceló el Face ID (no se envió nada).
    @discardableResult
    func decidir(id: String, herramienta: String, detalle: String, aprobar: Bool, motivo: String? = nil) async throws -> Bool {
        guard let api else { throw ErrorAPI.sinSesion }
        if aprobar && esPeligroso(herramienta: herramienta, detalle: detalle) {
            let r = await Autenticacion.comprobar(motivo: "Aprobar un comando peligroso")
            if r == .cancelado { return false }
        }
        do {
            _ = try await api.decidir(permiso: id, aprobar: aprobar, motivo: motivo)
        } catch ErrorAPI.sinSesion {
            sesionVencida()
            throw ErrorAPI.sinSesion
        }
        await leerUnaVez()
        return true
    }

    static let confirmarPorDefecto = [
        "rm", "rmdir", "del", "rd", "Remove-Item", "git push", "git reset --hard", "git clean",
        "deploy", "publish", "drop", "truncate", "format",
    ]

    // MARK: - Ir a otra pestaña

    func abrirFicha(_ id: String) {
        pestana = .oficina
        if rutaOficina.last != id { rutaOficina.append(id) }
    }

    /// "Dónde quedamos" vive en cada proyecto: abre el de esa carpeta.
    func abrirDonde(carpeta: String?) {
        pestana = .proyectos
        let lista = listaProyectos
        let p = lista.first { LogicaDonde.mismaCarpeta($0.donde?.datos.carpeta, carpeta) || LogicaDonde.mismaCarpeta($0.equipo?.ruta, carpeta) }
        rutaProyectos = p.map { [RutaProyecto(id: $0.id, seccion: .donde)] } ?? []
    }

    func abrirProyecto(equipo id: String, seccion: SeccionProyecto = .chat, aviso: String? = nil) {
        pestana = .proyectos
        rutaProyectos = [RutaProyecto(id: "e-" + id, seccion: seccion, aviso: aviso)]
    }

    // MARK: - Avisos de los orquestadores

    /// Lee los avisos y anuncia (una vez) los que no se habían visto. En la primera
    /// lectura solo se anotan, como la web al cargar la página.
    func leerAvisos() async {
        guard let api else { return }
        ultimaLecturaAvisos = Date()
        guard let lista = try? await api.avisosOrquestador() else { return }
        avisos = lista
        let r = LogicaAvisos.revisar(lista.map(\.clave), avisadas: LogicaAvisos.leerAvisadas(), primera: !avisosLeidos)
        avisosLeidos = true
        LogicaAvisos.guardarAvisadas(r.avisadas)
        // Cada clave nueva, una sola notificación nativa (salvo que su chat esté a la vista).
        let nuevos = r.nuevas.compactMap { c in lista.first { $0.clave == c } }
            .filter { LogicaAvisos.debeNotificar($0, chatAbierto: chatAbierto) }
        guard !nuevos.isEmpty else { return }
        let n = Notificador.compartido
        if await n.estado() == .notDetermined {
            if n.yaPreguntado { return }
            pendientesDeNotificar = nuevos
            pedirPermisoNotificaciones = true
            return
        }
        for a in nuevos { await n.mostrar(a) }
    }

    /// Avisos que esperan la respuesta al pedido de permiso de notificaciones.
    @ObservationIgnored private var pendientesDeNotificar: [AvisoOrquestador] = []
    /// La app explica para qué son las notificaciones antes del pedido del sistema.
    var pedirPermisoNotificaciones = false

    func responderPermisoNotificaciones(_ activar: Bool) async {
        pedirPermisoNotificaciones = false
        let pendientes = pendientesDeNotificar
        pendientesDeNotificar = []
        guard activar, await Notificador.compartido.pedirPermiso() else {
            UserDefaults.standard.set(true, forKey: "notificacionesPreguntadas")
            return
        }
        for a in pendientes where LogicaAvisos.debeNotificar(a, chatAbierto: chatAbierto) {
            await Notificador.compartido.mostrar(a)
        }
    }

    /// Al tocar una notificación: el chat de ese proyecto con la pregunta o la orden a la vista.
    func abrirDesdeNotificacion(proyecto: String, clave: String) {
        abrirProyecto(equipo: proyecto, seccion: .chat, aviso: clave)
    }

    /// Responder: el chat del proyecto con la pregunta (o la orden) a la vista.
    func responder(_ a: AvisoOrquestador) {
        Notificador.compartido.quitar(a.clave)
        abrirProyecto(equipo: a.proyecto_id, seccion: .chat, aviso: a.clave)
    }

    /// Ignorar o Esperar, guardado en el servidor.
    func atender(_ a: AvisoOrquestador, _ accion: AccionAviso) async throws {
        guard let api else { throw ErrorAPI.sinSesion }
        Notificador.compartido.quitar(a.clave)
        try await api.accionAviso(a.clave, accion)
        avisos.removeAll { $0.clave == a.clave }
        await leerAvisos()
    }

    // MARK: - Proyectos

    var listaProyectos: [ProyectoLista] {
        let donde = LogicaDonde.armar(proyectosMonitor ?? [], agentes)
        return LogicaProyectos.lista(equipos: proyectosEquipo ?? [], donde: donde, agentes: agentes)
    }

    func proyecto(_ id: String) -> ProyectoLista? { listaProyectos.first { $0.id == id } }

    /// Proyectos con equipo y, cada tanto, los del monitor y el consumo.
    func leerProyectos(todo: Bool = true) async {
        guard let api else { return }
        do {
            proyectosEquipo = try await api.proyectosEquipo()
            errorProyectos = nil
        } catch ErrorAPI.sinSesion {
            sesionVencida()
            return
        } catch let e as ErrorAPI {
            errorProyectos = e.mensaje
        } catch {}
        if todo || proyectosMonitor == nil {
            if let p = try? await api.proyectos() { proyectosMonitor = p }
            if let c = try? await api.consumo() { consumo = c }
        }
    }

    func reemplazar(_ p: ProyectoEquipo) {
        guard var lista = proyectosEquipo else { return }
        if let i = lista.firstIndex(where: { $0.id == p.id }) { lista[i] = p } else { lista.insert(p, at: 0) }
        proyectosEquipo = lista
    }
}
