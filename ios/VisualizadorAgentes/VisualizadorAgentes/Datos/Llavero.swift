import Foundation
import Security

/// La credencial en el Llavero de iOS (solo este dispositivo, tras el primer desbloqueo).
enum Llavero {
    private static let servicio = "com.inmersoft.visualizadoragentes"
    private static let cuenta = "sesion"

    private static func base() -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: servicio,
            kSecAttrAccount as String: cuenta,
        ]
    }

    static func leer() -> Credencial? {
        var q = base()
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var r: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &r) == errSecSuccess, let d = r as? Data else { return nil }
        return try? JSONDecoder().decode(Credencial.self, from: d)
    }

    @discardableResult
    static func guardar(_ c: Credencial) -> Bool {
        guard let d = try? JSONEncoder().encode(c) else { return false }
        SecItemDelete(base() as CFDictionary)
        var q = base()
        q[kSecValueData as String] = d
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    static func borrar() {
        SecItemDelete(base() as CFDictionary)
    }
}
