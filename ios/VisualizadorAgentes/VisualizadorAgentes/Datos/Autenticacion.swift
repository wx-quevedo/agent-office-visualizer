import Foundation
import LocalAuthentication

/// Face ID (o el código del iPhone si Face ID no está disponible).
enum Autenticacion {
    /// Hay Face ID o Touch ID configurado.
    static var hayBiometria: Bool {
        LAContext().canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
    }

    /// Hay algún modo de comprobar al dueño (biometría o código).
    static var hayBloqueo: Bool {
        LAContext().canEvaluatePolicy(.deviceOwnerAuthentication, error: nil)
    }

    /// Pide Face ID (con el código como respaldo). Sin bloqueo configurado en
    /// el iPhone no hay con qué comprobar: devuelve `sinBloqueo`.
    static func comprobar(motivo: String) async -> Resultado {
        let ctx = LAContext()
        ctx.localizedCancelTitle = "Cancelar"
        var error: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else { return .sinBloqueo }
        do {
            return try await ctx.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: motivo) ? .ok : .cancelado
        } catch {
            return .cancelado
        }
    }

    enum Resultado { case ok, cancelado, sinBloqueo }
}
