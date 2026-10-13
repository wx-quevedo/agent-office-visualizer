import Foundation
import Observation

/// El chat de un proyecto mientras está a la vista (Prompt 46): una lectura completa
/// al abrir (y cada 10 s, por las órdenes), el canal SSE para la respuesta en vivo y,
/// si el canal falla tres veces seguidas sin traer nada, la ruta liviana cada segundo.
/// Se detiene al salir del chat o al pasar a segundo plano.
@MainActor
@Observable
final class ChatVivo {
    private(set) var mensajes: [MensajeChat]?
    private(set) var ordenes: [Orden] = []
    private(set) var enVivo: EnVivo?
    private(set) var error: String?
    /// "sse" o "respaldo" (para el registro y las pruebas).
    private(set) var canal = "sse"

    @ObservationIgnored private var tareas: [Task<Void, Never>] = []
    @ObservationIgnored private var fallos = 0

    var burbuja: BurbujaVivo { LogicaChatVivo.burbuja(enVivo) }

    func iniciar(proyecto id: String, api: ClienteAPI, sinSesion: @escaping @MainActor () -> Void) {
        detener()
        fallos = 0
        canal = "sse"
        tareas.append(Task { [weak self] in
            while !Task.isCancelled {
                await self?.leerTodo(id, api, sinSesion)
                try? await Task.sleep(for: .seconds(10))
            }
        })
        tareas.append(Task { [weak self] in await self?.seguir(id, api, sinSesion) })
    }

    func detener() {
        tareas.forEach { $0.cancel() }
        tareas = []
    }

    /// El mensaje recién enviado, para mostrarlo con "Enviado" sin esperar la lectura.
    func agregar(_ m: MensajeChat) {
        mensajes = LogicaChatVivo.unir(mensajes ?? [], [m])
    }

    func reemplazar(_ o: Orden) {
        if let i = ordenes.firstIndex(where: { $0.id == o.id }) { ordenes[i] = o }
    }

    func leerTodo(_ id: String, _ api: ClienteAPI, _ sinSesion: @MainActor () -> Void) async {
        do {
            let c = try await api.chat(id)
            // Lo que trajo el canal en vivo entre medio no se pierde: se une por id.
            mensajes = LogicaChatVivo.unir(c.mensajes, (mensajes ?? []).filter { m in !c.mensajes.contains { $0.id == m.id } })
            ordenes = c.ordenes
            if let v = c.en_vivo { enVivo = v }
            error = nil
        } catch ErrorAPI.sinSesion {
            sinSesion()
        } catch let e as ErrorAPI {
            if mensajes == nil { error = e.mensaje }
        } catch {}
    }

    private func aplicar(_ e: ChatEnVivo) {
        mensajes = LogicaChatVivo.unir(mensajes ?? [], e.recientes)
        enVivo = e.en_vivo
    }

    private func seguir(_ id: String, _ api: ClienteAPI, _ sinSesion: @escaping @MainActor () -> Void) async {
        while !Task.isCancelled {
            if fallos >= LogicaChatVivo.fallosAntesDeRespaldo {
                canal = "respaldo"
                if LogicaChatVivo.debeSondear(enVivo, mensajes ?? []), let e = try? await api.chatEnVivo(id) {
                    aplicar(e)
                }
                try? await Task.sleep(for: .seconds(1))
                continue
            }
            var recibio = false
            do {
                for try await e in api.eventosChat(id) {
                    recibio = true
                    fallos = 0
                    aplicar(e)
                }
                // El servidor cierra a los 5 min: se vuelve a conectar enseguida. Si cerró
                // sin traer nada, cuenta como fallo.
                if !recibio {
                    fallos += 1
                    try? await Task.sleep(for: .seconds(1))
                }
            } catch is CancellationError {
                return
            } catch ErrorAPI.sinSesion {
                sinSesion()
                return
            } catch {
                if Task.isCancelled { return }
                if !recibio { fallos += 1 }
                try? await Task.sleep(for: .seconds(1)) // retry: 1000
            }
        }
    }
}
