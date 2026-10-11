import SwiftUI

// Colores de los bocetos (docs/bocetos/etapa-3). Solo tema claro.
extension Color {
    init(hex: UInt32) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }

    static let acento = Color(hex: 0x1D4FAF)
    static let naranja = Color(hex: 0x8A3E0E)
    static let rojo = Color(hex: 0x9B2C1E)
    static let verde = Color(hex: 0x2F5C45)
    static let texto = Color(hex: 0x1F2329)
    static let texto2 = Color(hex: 0x4A505C)
    static let texto3 = Color(hex: 0x2B2F36)
    static let fondo = Color(hex: 0xF4F5F7)
    static let fondo3D = Color(hex: 0xE9ECF1)
    static let borde = Color(hex: 0xE4E7EB)
    static let bordeCampo = Color(hex: 0xD5D9DF)
    static let separador = Color(hex: 0xEEF0F3)
    static let bordeAzul = Color(hex: 0x9DB8EE)
    static let bordeNaranja = Color(hex: 0xE8B98F)
    static let bordeRojo = Color(hex: 0xE4A69C)
    static let fondoActual = Color(hex: 0xE3ECFB)
    static let gris = Color(hex: 0x5A6170)
}

extension Tono {
    var color: Color {
        switch self {
        case .azul: return .acento
        case .naranja: return .naranja
        case .rojo: return .rojo
        case .verde: return .verde
        case .gris: return .texto2
        }
    }

    var borde: Color {
        switch self {
        case .azul: return .bordeAzul
        case .naranja: return .bordeNaranja
        case .rojo: return .bordeRojo
        default: return .borde
        }
    }
}

/// Tarjeta blanca de los bocetos.
struct Tarjeta<Contenido: View>: View {
    var borde: Color = .clear
    var grosor: CGFloat = 1
    var radio: CGFloat = 14
    @ViewBuilder var contenido: Contenido

    var body: some View {
        contenido
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white, in: RoundedRectangle(cornerRadius: radio))
            .overlay(RoundedRectangle(cornerRadius: radio).strokeBorder(borde, lineWidth: grosor))
    }
}

/// Título de sección en mayúsculas ("AHORA MISMO").
struct Rotulo: View {
    var texto: String
    var color: Color = .texto2
    var body: some View {
        Text(texto.uppercased())
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(color)
    }
}

/// Círculo con las iniciales del agente.
struct Iniciales: View {
    var texto: String
    var tamano: CGFloat = 40
    var body: some View {
        Text(texto)
            .font(.system(size: tamano * 0.35, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: tamano, height: tamano)
            .background(Color.texto3, in: Circle())
            .accessibilityHidden(true)
    }
}

extension Font {
    static func mono(_ tamano: CGFloat, _ peso: Font.Weight = .regular) -> Font {
        .system(size: tamano, weight: peso, design: .monospaced)
    }
}
