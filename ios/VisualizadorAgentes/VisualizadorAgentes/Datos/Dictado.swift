import AVFoundation
import Foundation
import Observation
import Speech

/// Dictado de ideas con el reconocimiento de voz de Apple en español, en el
/// iPhone cuando el idioma lo permite (sin enviar el audio a Apple).
@MainActor
@Observable
final class Dictado {
    private(set) var escuchando = false
    private(set) var texto = ""
    private(set) var error: String?
    /// El reconocimiento corre en el propio iPhone.
    private(set) var enDispositivo = false

    @ObservationIgnored private let motor = AVAudioEngine()
    @ObservationIgnored private var pedido: SFSpeechAudioBufferRecognitionRequest?
    @ObservationIgnored private var tarea: SFSpeechRecognitionTask?
    @ObservationIgnored private var reconocedor: SFSpeechRecognizer?

    /// Español latino si está disponible; si no, el de España.
    static func reconocedorEspanol() -> SFSpeechRecognizer? {
        let ids = ["es-419", "es-MX", "es-US", "es-ES"]
        let todos = ids.compactMap { SFSpeechRecognizer(locale: Locale(identifier: $0)) }
        // Primero uno que funcione en el iPhone, luego uno disponible, luego cualquiera.
        return todos.first { $0.supportsOnDeviceRecognition && $0.isAvailable }
            ?? todos.first { $0.isAvailable } ?? todos.first
    }

    func alternar() async {
        if escuchando { detener() } else { await empezar() }
    }

    func empezar() async {
        error = nil
        texto = ""
        guard await Self.pedirPermisoVoz() else {
            error = "Sin permiso de reconocimiento de voz. Actívalo en Ajustes, Agentes."
            return
        }
        guard await AVAudioApplication.requestRecordPermission() else {
            error = "Sin permiso de micrófono. Actívalo en Ajustes, Agentes."
            return
        }
        guard let r = Self.reconocedorEspanol() else {
            error = "El reconocimiento de voz en español no está disponible ahora."
            return
        }
        reconocedor = r
        do {
            let sesion = AVAudioSession.sharedInstance()
            try sesion.setCategory(.record, mode: .measurement, options: .duckOthers)
            try sesion.setActive(true, options: .notifyOthersOnDeactivation)

            let p = SFSpeechAudioBufferRecognitionRequest()
            p.shouldReportPartialResults = true
            p.addsPunctuation = true
            if r.supportsOnDeviceRecognition {
                p.requiresOnDeviceRecognition = true
                enDispositivo = true
            } else {
                enDispositivo = false
            }
            pedido = p

            let entrada = motor.inputNode
            let formato = entrada.outputFormat(forBus: 0)
            entrada.removeTap(onBus: 0)
            entrada.installTap(onBus: 0, bufferSize: 1024, format: formato) { [weak p] buffer, _ in
                p?.append(buffer)
            }
            motor.prepare()
            try motor.start()
            escuchando = true

            tarea = r.recognitionTask(with: p) { [weak self] resultado, falla in
                let parcial = resultado?.bestTranscription.formattedString
                let final = resultado?.isFinal ?? false
                Task { @MainActor in
                    guard let self else { return }
                    if let parcial { self.texto = parcial }
                    if falla != nil && parcial == nil && self.texto.isEmpty {
                        self.error = "No se pudo reconocer la voz. Revisa la conexión o escribe la idea."
                    }
                    if falla != nil || final { self.detener() }
                }
            }
        } catch {
            self.error = "No se pudo usar el micrófono."
            detener()
        }
    }

    func detener() {
        guard escuchando || pedido != nil else { return }
        motor.stop()
        motor.inputNode.removeTap(onBus: 0)
        pedido?.endAudio()
        tarea?.finish()
        pedido = nil
        tarea = nil
        escuchando = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    private static func pedirPermisoVoz() async -> Bool {
        switch SFSpeechRecognizer.authorizationStatus() {
        case .authorized: return true
        case .denied, .restricted: return false
        default:
            return await withCheckedContinuation { c in
                SFSpeechRecognizer.requestAuthorization { c.resume(returning: $0 == .authorized) }
            }
        }
    }
}
