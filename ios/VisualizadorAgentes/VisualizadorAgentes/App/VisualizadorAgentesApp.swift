import SwiftUI

@main
struct VisualizadorAgentesApp: App {
    @State private var modelo = ModeloApp()
    @Environment(\.scenePhase) private var fase

    var body: some Scene {
        WindowGroup {
            Raiz()
                .environment(modelo)
                .preferredColorScheme(.light)
                .tint(.acento)
                .onChange(of: fase) { _, nueva in
                    switch nueva {
                    case .active: modelo.iniciar()
                    case .background: modelo.alPasarAFondo()
                    default: break
                    }
                }
        }
    }
}

struct Raiz: View {
    @Environment(ModeloApp.self) private var modelo

    var body: some View {
        ZStack {
            if modelo.credencial == nil {
                EntrarVista()
            } else {
                Pestanas()
                if modelo.bloqueada { BloqueoVista() }
            }
        }
        .animation(.default, value: modelo.credencial == nil)
    }
}

struct Pestanas: View {
    @Environment(ModeloApp.self) private var modelo

    var body: some View {
        @Bindable var m = modelo
        TabView(selection: $m.pestana) {
            Tab("Oficina", systemImage: "building.2", value: Pestana.oficina) {
                OficinaVista()
            }
            Tab("Decisiones", systemImage: "checkmark.circle", value: Pestana.decisiones) {
                DecisionesVista()
            }
            .badge(modelo.pendientes)
            Tab("Dónde quedamos", systemImage: "map", value: Pestana.donde) {
                DondeVista()
            }
            Tab("Ideas", systemImage: "lightbulb", value: Pestana.ideas) {
                IdeasVista()
            }
        }
    }
}

struct BloqueoVista: View {
    @Environment(ModeloApp.self) private var modelo

    var body: some View {
        VStack(spacing: 20) {
            Spacer()
            Image(systemName: "faceid")
                .font(.system(size: 56))
                .foregroundStyle(Color.acento)
            Text("Oficina bloqueada").font(.system(size: 22, weight: .bold))
            Button("Desbloquear") { Task { await modelo.desbloquear() } }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
        .task { await modelo.desbloquear() }
    }
}
