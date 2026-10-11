import Foundation

// Formas de los endpoints del backend (las mismas que usa la web en
// frontend/src/components/*/logica.ts). Casi todo es opcional: el motor y el
// monitor agregan campos con el tiempo y la app no debe romperse por eso.

/// Valor JSON libre (la evidencia de una espera trae claves variables).
enum ValorJSON: Codable, Equatable, Sendable {
    case texto(String)
    case numero(Double)
    case booleano(Bool)
    case objeto([String: ValorJSON])
    case lista([ValorJSON])
    case nulo

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .nulo }
        else if let b = try? c.decode(Bool.self) { self = .booleano(b) }
        else if let n = try? c.decode(Double.self) { self = .numero(n) }
        else if let s = try? c.decode(String.self) { self = .texto(s) }
        else if let l = try? c.decode([ValorJSON].self) { self = .lista(l) }
        else { self = .objeto(try c.decode([String: ValorJSON].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .texto(let s): try c.encode(s)
        case .numero(let n): try c.encode(n)
        case .booleano(let b): try c.encode(b)
        case .objeto(let o): try c.encode(o)
        case .lista(let l): try c.encode(l)
        case .nulo: try c.encodeNil()
        }
    }

    var texto: String? {
        if case .texto(let s) = self { return s }
        return nil
    }
}

// MARK: - GET /agents/state

struct EstadoOficina: Codable, Equatable, Sendable {
    var generado: String?
    var presencia: Presencia?
    var agentes: [Agente]
    /// Conteo de la bandeja de Decisiones (Prompt 33), para la insignia.
    var decisiones_pendientes: Int?
}

struct Presencia: Codable, Equatable, Sendable {
    var estado: String
    var motivo: String?
    var dispositivos: [String]?
}

struct Agente: Codable, Equatable, Identifiable, Sendable {
    struct Datos: Codable, Equatable, Sendable {
        var session_id: String
        var proyecto: String?
        var cuenta: String?
        var maquina: String?
        var modelo: String?
    }

    struct EstadoMotor: Codable, Equatable, Sendable {
        var numero: Int
        var nombre: String
        var desde: String?
    }

    struct Espera: Codable, Equatable, Sendable {
        var tipo: String?
        var evidencia: [String: ValorJSON]?
    }

    struct EsperaDetalle: Codable, Equatable, Sendable {
        var texto: String
        var base: String
        var segundos: Double
        var limite_min: Double?
    }

    struct Atasco: Codable, Equatable, Sendable {
        var tipo: String?
        var motivo: String
        var desde: String?
        var ultimos_intentos: [String]?
        var ultimo_error: String?
    }

    struct UltimoEvento: Codable, Equatable, Sendable {
        var tipo: String?
        var hora: String?
    }

    struct Cierre: Codable, Equatable, Sendable {
        var motivo: String
        var desde: String?
    }

    struct Indicadores: Codable, Equatable, Sendable {
        var tokens_por_minuto: Double?
        var tokens_totales: Double?
        var errores_seguidos: Int?
    }

    struct EventoReciente: Codable, Equatable, Sendable {
        var hora: String?
        var tipo: String?
        var herramienta: String?
        var detalle: String?
    }

    struct Resumen: Codable, Equatable, Sendable {
        var clave: String?
        var estado: String
        var texto: String?
    }

    var agente: Datos
    var estado: EstadoMotor
    var espera: Espera?
    var espera_detalle: EsperaDetalle?
    var atasco: Atasco?
    var trabajo_continuo_s: Double?
    var herramienta_actual: String?
    var ultimo_evento: UltimoEvento?
    var pregunta_pendiente: String?
    var pregunta_opciones: [PreguntaAgente]?
    var cierre: Cierre?
    var indicadores: Indicadores?
    var eventos_recientes: [EventoReciente]?
    var permiso: Permiso?
    var resumenes: [String: Resumen]?

    var id: String { agente.session_id }
}

// MARK: - Preguntas (AskUserQuestion), solo lectura

struct PreguntaAgente: Codable, Equatable, Sendable {
    struct Opcion: Codable, Equatable, Sendable {
        var etiqueta: String
        var descripcion: String?
    }

    var texto: String
    var encabezado: String?
    var opciones: [Opcion]
    var multiple: Bool?
}

// MARK: - GET /decisiones

struct Bandeja: Codable, Equatable, Sendable {
    struct Conteo: Codable, Equatable, Sendable {
        var permiso: Int?
        var pregunta: Int?
        var atasco: Int?
        var total: Int
    }

    var pendientes: [Decision]
    var conteo: Conteo?
    var resueltas_hoy: [Resuelta]
}

struct Decision: Codable, Equatable, Identifiable, Sendable {
    struct PermisoItem: Codable, Equatable, Sendable {
        var id: String?
        var herramienta: String?
        var esperando: Bool
        var segundos_restantes: Int?
        var estado: String?
    }

    struct PreguntaItem: Codable, Equatable, Sendable {
        var texto: String?
        var preguntas: [PreguntaAgente]
        var responder_en: String?
    }

    struct AtascoItem: Codable, Equatable, Sendable {
        var tipo: String?
        var motivo: String?
        var ultimo_intento: String?
        var ultimo_error: String?
    }

    var tipo: String // permiso, pregunta, atasco
    var id: String
    var session_id: String
    var proyecto: String?
    var carpeta: String?
    var cuenta: String?
    var maquina: String?
    var desde: String?
    var hace_s: Double?
    var resumen: String?
    var detalle: String?
    var permiso: PermisoItem?
    var pregunta: PreguntaItem?
    var atasco: AtascoItem?
}

struct Resuelta: Codable, Equatable, Identifiable, Sendable {
    var tipo: String
    var id: String
    var proyecto: String?
    var cuenta: String?
    var maquina: String?
    var texto: String?
    var como: String?
    var motivo: String?
    var quien: String?
    var cuando: String?
}

// MARK: - Ideas

struct Idea: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var texto: String
    var proyecto: String?
    var origen: String?
    var estado: String // nueva, asignada, archivada
    var creada: String?
    var actualizada: String?
}

struct IdeasRespuesta: Codable, Equatable, Sendable {
    var ideas: [Idea]
    var proyectos: [String]
}

// MARK: - Permisos

struct Permiso: Codable, Equatable, Sendable {
    var id: String
    var session_id: String?
    var herramienta: String
    var detalle: String
    var creada: String?
    var esperando: Bool
    var vence: String?
    var estado: String
    var motivo: String?
    var dispositivo: String?
}

struct ConfigPermisos: Codable, Equatable, Sendable {
    var politica: String?
    var espera_seg: Int?
    var confirmar: [String]
}

// MARK: - GET /agents/{id}/historial

struct Turno: Codable, Equatable, Sendable {
    struct Commit: Codable, Equatable, Sendable {
        var hora: String?
        var mensaje: String?
    }

    var numero: Int
    var inicio: String
    var fin: String?
    var duracion_s: Double?
    var pedido: String?
    var total_herramientas: Int?
    var commits: [Commit]?
    var errores: Int?
    var tokens_salida: Double?
    var resultado: String
    var pregunta: String?
}

struct Historial: Codable, Equatable, Sendable {
    var session_id: String?
    var pagina: Int?
    var total: Int?
    var turnos: [Turno]
}

// MARK: - GET /consumo

struct Consumo: Codable, Equatable, Sendable {
    struct Total: Codable, Equatable, Sendable {
        var sesiones: Int?
        var tokens_salida: Double
        var segundos_trabajo: Double?
        var segundos_con_agentes: Double
    }

    struct PorSesion: Codable, Equatable, Sendable {
        var session_id: String
        var proyecto: String?
        var tokens_salida: Double
        var segundos_trabajo: Double
        var continuo_s: Double?
    }

    var dia: String?
    var total: Total
    var por_sesion: [PorSesion]
}

// MARK: - GET /proyectos

struct ProyectosRespuesta: Codable, Equatable, Sendable {
    var proyectos: [ProyectoApi]
}

struct ProyectoApi: Codable, Equatable, Sendable {
    struct ItemPlan: Codable, Equatable, Sendable {
        var nombre: String
        var estado: String
    }

    struct PromptPlan: Codable, Equatable, Sendable {
        var numero: Int
        var nombre: String
        var estado: String
        var fecha: String?
        var commits: [String]?
    }

    struct PromptTurnos: Codable, Equatable, Sendable {
        var numero: Int
        var nombre: String?
        var inicio: String?
        var duracion_s: Double?
        var commits: [Turno.Commit]?
        var resultado: String
    }

    struct UltimoCommit: Codable, Equatable, Sendable {
        var hash: String
        var mensaje: String?
        var fecha: String?
    }

    struct UltimaActividad: Codable, Equatable, Sendable {
        var session_id: String?
        var estado: String?
        var ultimo_evento: String?
        var ultimo_turno: Turno?
    }

    var carpeta: String
    var maquina: String?
    var tiene_project_md: Bool
    var titulo: String?
    var plan: [ItemPlan]
    var posicion: String?
    var siguiente_paso: String?
    var espera_decision: [String]
    var ultimo_commit: UltimoCommit?
    var ultima_actividad: UltimaActividad?
    var prompts: [PromptPlan]?
    var prompts_turnos: [PromptTurnos]?

    init(
        carpeta: String, maquina: String? = nil, tiene_project_md: Bool = false,
        titulo: String? = nil, plan: [ItemPlan] = [], posicion: String? = nil,
        siguiente_paso: String? = nil, espera_decision: [String] = [],
        ultimo_commit: UltimoCommit? = nil, ultima_actividad: UltimaActividad? = nil,
        prompts: [PromptPlan]? = nil, prompts_turnos: [PromptTurnos]? = nil
    ) {
        self.carpeta = carpeta
        self.maquina = maquina
        self.tiene_project_md = tiene_project_md
        self.titulo = titulo
        self.plan = plan
        self.posicion = posicion
        self.siguiente_paso = siguiente_paso
        self.espera_decision = espera_decision
        self.ultimo_commit = ultimo_commit
        self.ultima_actividad = ultima_actividad
        self.prompts = prompts
        self.prompts_turnos = prompts_turnos
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        carpeta = try c.decode(String.self, forKey: .carpeta)
        maquina = try c.decodeIfPresent(String.self, forKey: .maquina)
        tiene_project_md = try c.decodeIfPresent(Bool.self, forKey: .tiene_project_md) ?? false
        titulo = try c.decodeIfPresent(String.self, forKey: .titulo)
        plan = try c.decodeIfPresent([ItemPlan].self, forKey: .plan) ?? []
        posicion = try c.decodeIfPresent(String.self, forKey: .posicion)
        siguiente_paso = try c.decodeIfPresent(String.self, forKey: .siguiente_paso)
        espera_decision = try c.decodeIfPresent([String].self, forKey: .espera_decision) ?? []
        ultimo_commit = try c.decodeIfPresent(UltimoCommit.self, forKey: .ultimo_commit)
        ultima_actividad = try c.decodeIfPresent(UltimaActividad.self, forKey: .ultima_actividad)
        prompts = try c.decodeIfPresent([PromptPlan].self, forKey: .prompts)
        prompts_turnos = try c.decodeIfPresent([PromptTurnos].self, forKey: .prompts_turnos)
    }
}

// MARK: - Fechas

/// Fechas ISO 8601 del backend (Python: "2026-10-11T19:55:32.326000+00:00",
/// a veces sin fracción o con "Z").
enum FechaISO {
    private static let conFraccion: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let sinFraccion: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func leer(_ texto: String?) -> Date? {
        guard var s = texto?.trimmingCharacters(in: .whitespaces), !s.isEmpty else { return nil }
        // Fracción de más de 3 dígitos (microsegundos de Python): se recorta a 3.
        if let punto = s.firstIndex(of: "."),
           let fin = s[punto...].firstIndex(where: { $0 == "+" || $0 == "-" || $0 == "Z" }) {
            let digitos = s[s.index(after: punto)..<fin]
            if digitos.count > 3 {
                s.replaceSubrange(punto..<fin, with: "." + digitos.prefix(3))
            }
        }
        // Sin zona: se toma como UTC.
        let tieneZona = s.hasSuffix("Z") || s.range(of: #"[+-]\d{2}:?\d{2}$"#, options: .regularExpression) != nil
        if !tieneZona { s += "Z" }
        return conFraccion.date(from: s) ?? sinFraccion.date(from: s)
    }
}
