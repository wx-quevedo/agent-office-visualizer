import Foundation

// Etapa 4: proyectos con equipo (orquestador y agentes de código), chat, órdenes
// y reglas de la casa. Mismas formas que backend/app/api/routes/proyectos_equipo.py
// y frontend/src/components/proyectos/logica.ts.

struct ProyectoEquipo: Codable, Equatable, Identifiable, Sendable {
    struct Miembro: Codable, Equatable, Identifiable, Sendable {
        struct Oficina: Codable, Equatable, Sendable {
            var numero: Int
            var nombre: String
            var desde: String?
            var espera: String?
        }

        var id: String
        var rol: String // orquestador, agente
        var nombre: String
        var modelo: String
        var esfuerzo: String
        var session_id: String?
        var estado: String // pendiente, activo, pausado, detenido, error
        var orden: Int?
        var oficina: Oficina?
    }

    var id: String
    var nombre: String
    var maquina: String
    var cuenta: String
    var ruta: String?
    var plantilla: String?
    var estado: String // creando, activo, pausando, pausado, reanudando, deteniendo, detenido, error
    var auto_aprobar: Bool
    var error: String?
    var creado: String?
    var actualizado: String?
    var haciendo: String?
    var ordenes_por_aprobar: Int?
    var equipo: [Miembro]
}

struct ProyectosEquipoRespuesta: Codable, Equatable, Sendable {
    var proyectos: [ProyectoEquipo]
}

struct MaquinaEquipo: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var nombre: String
    var sistema: String?
    var encendida: Bool
    var ruta_base: String?
    var disponible: Bool
    var motivo: String?
}

struct MaquinasRespuesta: Codable, Equatable, Sendable {
    var maquinas: [MaquinaEquipo]
}

/// Cuerpo de POST /proyectos-creados.
struct NuevoProyecto: Codable, Equatable, Sendable {
    struct Config: Codable, Equatable, Sendable {
        var modelo: String
        var esfuerzo: String
    }

    var nombre: String
    var maquina: String
    var cuenta: String
    var plantilla: String
    var orquestador: Config
    var agentes: [Config]
    var auto_aprobar: Bool
}

// MARK: - Chat y órdenes

struct MensajeChat: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var autor: String // washington, orquestador
    var texto: String
    var creado: String
}

struct Orden: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var proyecto_id: String
    var proyecto: String?
    var numero: Int
    var agente: String
    var texto_propuesto: String
    var texto_final: String?
    var texto: String
    var editada: Bool?
    var estimado: String?
    var dificultad: String?
    var estado: String // por_aprobar, aprobada, rechazada, en_curso, terminada, fallida
    var motivo: String?
    var decidido_por: String?
    var decidido: String?
    var resumen: String?
    var creado: String
    var actualizado: String?
}

struct ChatRespuesta: Codable, Equatable, Sendable {
    var mensajes: [MensajeChat]
    var ordenes: [Orden]
}

// MARK: - Reglas de la casa

struct ReglaProyecto: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var texto: String
    var tipo: String
    var activa_por_defecto: Bool
    var orden: Int?
    var activa: Bool
    var ajustada: Bool?
}

struct ComandoProyecto: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var comando: String
    var activo_por_defecto: Bool
    var activo: Bool
}

struct ReglasDeProyecto: Codable, Equatable, Sendable {
    var reglas: [ReglaProyecto]
    var comandos: [ComandoProyecto]?
}

struct Regla: Codable, Equatable, Identifiable, Sendable {
    var id: String
    var texto: String
    var tipo: String
    var activa_por_defecto: Bool
}

struct ReglasRespuesta: Codable, Equatable, Sendable {
    var reglas: [Regla]
    var tipos: [String]
}
