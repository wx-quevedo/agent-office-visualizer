import SwiftUI

/// Pantalla Entrar (boceto Acceso): servidor, contraseña y Face ID.
struct EntrarVista: View {
    @Environment(ModeloApp.self) private var modelo
    @State private var servidor = "agents.example.com"
    @State private var contrasena = ""
    @State private var faceID = true
    @State private var enviando = false
    @State private var error: String?
    @FocusState private var foco: Campo?

    enum Campo { case servidor, contrasena }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                VStack(alignment: .leading, spacing: 10) {
                    Image(systemName: "building.2.fill")
                        .font(.system(size: 28, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(width: 64, height: 64)
                        .background(Color.acento, in: RoundedRectangle(cornerRadius: 16))
                        .accessibilityHidden(true)
                    Text("Visualizador de Agentes")
                        .font(.system(size: 30, weight: .bold))
                    Text("Tu organización de agentes, en el bolsillo.")
                        .font(.system(size: 16))
                        .foregroundStyle(Color.texto2)
                }

                VStack(alignment: .leading, spacing: 14) {
                    campo("Servidor") {
                        TextField("agents.example.com", text: $servidor)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .keyboardType(.URL)
                            .textContentType(.URL)
                            .focused($foco, equals: .servidor)
                            .submitLabel(.next)
                            .onSubmit { foco = .contrasena }
                    }
                    campo("Contraseña") {
                        SecureField("", text: $contrasena)
                            .textContentType(.password)
                            .focused($foco, equals: .contrasena)
                            .submitLabel(.go)
                            .onSubmit(enviar)
                            .accessibilityIdentifier("contrasena")
                    }
                    if let error {
                        Text(error)
                            .font(.system(size: 14))
                            .foregroundStyle(Color.rojo)
                    }
                    Button(action: enviar) {
                        ZStack {
                            Text("Entrar").opacity(enviando ? 0 : 1)
                            if enviando { ProgressView().tint(.white) }
                        }
                        .font(.system(size: 17, weight: .semibold))
                        .frame(maxWidth: .infinity, minHeight: 50)
                        .foregroundStyle(.white)
                        .background(Color.acento, in: RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(enviando || contrasena.isEmpty)
                    .opacity(contrasena.isEmpty ? 0.6 : 1)
                    .padding(.top, 6)
                }

                VStack(alignment: .leading, spacing: 10) {
                    Toggle("Usar Face ID para abrir la app", isOn: $faceID)
                        .font(.system(size: 15))
                        .tint(.verde)
                    Text("La sesión dura 30 días en este iPhone. Aprobar un permiso peligroso siempre pide Face ID.")
                        .font(.system(size: 13))
                        .foregroundStyle(Color.texto2)
                }
                .padding(14)
                .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(Color.borde))

                Text("Solo tú tienes acceso. Puedes cerrar esta sesión desde la web, en la lista de sesiones activas.")
                    .font(.system(size: 13))
                    .foregroundStyle(Color.texto2)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
            }
            .padding(.horizontal, 24)
            .padding(.top, 64)
            .padding(.bottom, 32)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
    }

    private func campo<C: View>(_ titulo: String, @ViewBuilder _ control: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(titulo)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(Color.texto2)
            control()
                .font(.system(size: 16))
                .padding(.horizontal, 14)
                .frame(height: 48)
                .background(Color.white, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color.bordeCampo))
        }
    }

    private func enviar() {
        guard !enviando, !contrasena.isEmpty else { return }
        guard let url = ClienteAPI.normalizarServidor(servidor) else {
            error = "Escribe la dirección del servidor, por ejemplo agents.example.com."
            return
        }
        error = nil
        enviando = true
        let clave = contrasena
        Task {
            defer { enviando = false }
            do {
                try await modelo.entrar(servidor: url, contrasena: clave, faceID: faceID)
                contrasena = ""
            } catch let e as ErrorAPI {
                error = e.mensaje
            } catch {
                self.error = ErrorAPI.red.mensaje
            }
        }
    }
}
