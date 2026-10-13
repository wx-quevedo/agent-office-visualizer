import Foundation
import UserNotifications
import os

private let registro = Logger(subsystem: "com.inmersoft.visualizadoragentes", category: "notificaciones")

/// Notificaciones nativas de iOS para los avisos de los orquestadores (Prompt 46).
/// Son locales: salen mientras la app está abierta o recién en segundo plano. Con la
/// app cerrada no llegan hasta tener push remoto (Prompt 32).
@MainActor
final class Notificador: NSObject, UNUserNotificationCenterDelegate {
    static let compartido = Notificador()
    private static let clavePreguntado = "notificacionesPreguntadas"

    /// Al tocar una notificación: (proyecto_id, clave del aviso). Si la app todavía no
    /// lo instaló (abrió desde la notificación), el toque queda guardado hasta entonces.
    var alTocar: ((String, String) -> Void)? {
        didSet {
            if let alTocar, let p = pendiente {
                pendiente = nil
                alTocar(p.0, p.1)
            }
        }
    }
    private var pendiente: (String, String)?

    func tocada(_ proyecto: String, _ clave: String) {
        registro.notice("abrir chat \(proyecto, privacy: .public) en \(clave, privacy: .public)")
        if let alTocar { alTocar(proyecto, clave) } else { pendiente = (proyecto, clave) }
    }

    private var centro: UNUserNotificationCenter { .current() }

    func instalar() {
        centro.delegate = self
    }

    func estado() async -> UNAuthorizationStatus {
        await centro.notificationSettings().authorizationStatus
    }

    /// La app ya mostró su explicación y el pedido del sistema (no se vuelve a preguntar).
    var yaPreguntado: Bool { UserDefaults.standard.bool(forKey: Self.clavePreguntado) }

    func pedirPermiso() async -> Bool {
        UserDefaults.standard.set(true, forKey: Self.clavePreguntado)
        return (try? await centro.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    /// Una notificación por aviso: el identificador es la clave, así nunca se repite.
    func mostrar(_ a: AvisoOrquestador) async {
        let e = await estado()
        guard e == .authorized || e == .provisional else { return }
        let c = LogicaAvisos.contenido(a)
        let n = UNMutableNotificationContent()
        n.title = c.titulo
        n.body = c.cuerpo
        n.sound = .default
        n.threadIdentifier = a.proyecto_id
        n.userInfo = ["clave": a.clave, "proyecto_id": a.proyecto_id]
        try? await centro.add(UNNotificationRequest(identifier: c.id, content: n, trigger: nil))
    }

    /// Ya atendido (Responder, Ignorar o Esperar): se quita del centro de notificaciones.
    func quitar(_ clave: String) {
        centro.removeDeliveredNotifications(withIdentifiers: [clave])
    }

    // MARK: - UNUserNotificationCenterDelegate

    /// También con la app abierta: banner nativo, que se quita deslizando hacia arriba.
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                            withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list, .sound])
    }

    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                            withCompletionHandler completionHandler: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        registro.notice("toque en notificación: \(response.actionIdentifier, privacy: .public)")
        let proyecto = info["proyecto_id"] as? String
        let clave = info["clave"] as? String
        DispatchQueue.main.async {
            if let proyecto, let clave {
                MainActor.assumeIsolated { Notificador.compartido.tocada(proyecto, clave) }
            }
            completionHandler()
        }
    }
}
