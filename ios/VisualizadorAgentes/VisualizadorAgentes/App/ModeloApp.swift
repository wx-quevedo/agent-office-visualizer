import Foundation
import Observation
import UIKit

enum Pestana: Hashable { case oficina, decisiones, donde, ideas }

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
    var proyectoElegido: String?

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

    /// Insignia de Decisiones: el conteo de la bandeja que trae /agents/state.
    var pendientes: Int { estado?.decisiones_pendientes ?? Logica.pendientes(visibles) }

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

    func abrirDonde(carpeta: String?) {
        proyectoElegido = carpeta.map(LogicaDonde.idProyecto)
        pestana = .donde
    }
}
