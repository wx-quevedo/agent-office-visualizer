import SwiftUI

enum ModoOficina: String, CaseIterable, Identifiable {
    case lista = "Lista"
    case tresD = "3D"
    var id: String { rawValue }
}

/// Pestaña Oficina: la escena 3D (la app abre aquí) o la lista, y la ficha encima.
struct OficinaVista: View {
    @Environment(ModeloApp.self) private var modelo
    @State private var modo: ModoOficina = .tresD

    var body: some View {
        @Bindable var m = modelo
        NavigationStack(path: $m.rutaOficina) {
            Group {
                switch modo {
                case .tresD: Oficina3DVista(modo: $modo)
                case .lista: OficinaListaVista(modo: $modo)
                }
            }
            .navigationTitle("Oficina")
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: String.self) { id in
                FichaVista(id: id)
            }
        }
    }
}

/// Título, conteo y selector Lista | 3D (como los bocetos Main y Oficina3D).
struct EncabezadoOficina: View {
    @Environment(ModeloApp.self) private var modelo
    @Binding var modo: ModoOficina
    var agentes: [Agente]

    var body: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Oficina")
                    .font(.system(size: 34, weight: .bold))
                Text(modelo.estado == nil ? "Conectando…" : Logica.resumenConteo(agentes))
                    .font(.system(size: 15))
                    .foregroundStyle(Color.texto2)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 8) {
                Picker("Vista", selection: $modo) {
                    ForEach(ModoOficina.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(width: 120)
                Menu {
                    Button("Cerrar sesión", systemImage: "rectangle.portrait.and.arrow.right", role: .destructive) {
                        modelo.salir()
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .font(.system(size: 20))
                        .foregroundStyle(Color.texto2)
                        .frame(width: 44, height: 28, alignment: .trailing)
                }
                .accessibilityLabel("Más opciones")
            }
        }
        .foregroundStyle(Color.texto)
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }
}

/// Aviso de conexión cortada (la lectura reintenta sola).
struct AvisoConexion: View {
    @Environment(ModeloApp.self) private var modelo
    var body: some View {
        if modelo.sinConexion {
            Label("Sin conexión con la oficina. Reintentando…", systemImage: "wifi.exclamationmark")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Color.naranja)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color.white, in: Capsule())
                .overlay(Capsule().strokeBorder(Color.bordeNaranja))
        }
    }
}

// MARK: - Oficina 3D

struct Oficina3DVista: View {
    @Environment(ModeloApp.self) private var modelo
    @Binding var modo: ModoOficina

    var body: some View {
        ZStack(alignment: .top) {
            if let c = modelo.credencial {
                OficinaWebVista(web: web(c))
                    .ignoresSafeArea()
            }
            VStack(spacing: 6) {
                EncabezadoOficina(modo: $modo, agentes: modelo.visibles)
                AvisoConexion()
            }
            .padding(.bottom, 10)
            .background(
                LinearGradient(colors: [Color.fondo3D, Color.fondo3D.opacity(0.85), Color.fondo3D.opacity(0)],
                               startPoint: .top, endPoint: .bottom)
                    .ignoresSafeArea(edges: .top)
            )
        }
        .safeAreaInset(edge: .bottom) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Arrastra para girar · pellizca para acercar")
                    .font(.system(size: 12))
                    .foregroundStyle(Color.texto2)
                    .padding(.horizontal, 16)
                    .allowsHitTesting(false)
                TarjetaTeEsperan(agentes: Logica.teEsperan(modelo.visibles), compacta: true)
                    .padding(.horizontal, 12)
            }
            .padding(.bottom, 8)
        }
        .background(Color.fondo3D)
    }

    private func web(_ c: Credencial) -> OficinaWeb {
        let w = OficinaWeb.compartida(c)
        w.alTocarAgente = { [modelo] id in modelo.abrirFicha(id) }
        w.alPerderSesion = { [modelo] in modelo.sesionVencida() }
        return w
    }
}

// MARK: - Te esperan

struct TarjetaTeEsperan: View {
    @Environment(ModeloApp.self) private var modelo
    var agentes: [Agente]
    var compacta = false

    var body: some View {
        if !agentes.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                Text("TE ESPERAN · \(agentes.count)")
                    .font(.system(size: compacta ? 12 : 13, weight: compacta ? .bold : .semibold))
                    .tracking(compacta ? 0.4 : 0)
                    .foregroundStyle(Color.acento)
                    .padding(.horizontal, 14)
                    .padding(.top, compacta ? 10 : 12)
                    .padding(.bottom, 4)
                ForEach(Array(agentes.prefix(compacta ? 3 : 6).enumerated()), id: \.element.id) { i, a in
                    if i > 0 { Divider().overlay(Color.separador) }
                    NavigationLink(value: a.id) { fila(a) }
                        .buttonStyle(.plain)
                }
            }
            .padding(.bottom, 4)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white, in: RoundedRectangle(cornerRadius: compacta ? 16 : 14))
            .overlay(RoundedRectangle(cornerRadius: compacta ? 16 : 14).strokeBorder(Color.bordeAzul))
            .shadow(color: compacta ? Color.black.opacity(0.08) : .clear, radius: 12, y: 4)
        }
    }

    private func color(_ a: Agente) -> Color { a.estado.numero == 13 ? .acento : .naranja }

    @ViewBuilder
    private func fila(_ a: Agente) -> some View {
        let nombre = Logica.nombre(a)
        let pide = Logica.loQuePide(a)
        let tiempo = Logica.segundosDesde(a.estado.desde, ahora: modelo.ahora).map(Logica.tiempoCorto) ?? ""
        HStack(spacing: compacta ? 10 : 12) {
            Circle().fill(color(a)).frame(width: compacta ? 9 : 10, height: compacta ? 9 : 10)
            if compacta {
                Text("\(Text(nombre).bold()) · \(pide)")
                    .font(.system(size: 14))
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Text(tiempo).font(.system(size: 12)).foregroundStyle(Color.texto2)
            } else {
                VStack(alignment: .leading, spacing: 2) {
                    Text(a.estado.numero == 13 ? "\(nombre) pide permiso" : "\(nombre) pregunta")
                        .font(.system(size: 15, weight: .semibold))
                    Text("\(pide) · hace \(tiempo)")
                        .font(.system(size: 13))
                        .foregroundStyle(Color.texto2)
                        .lineLimit(2)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color.bordeCampo)
            }
        }
        .foregroundStyle(Color.texto)
        .padding(.horizontal, 14)
        .padding(.vertical, compacta ? 8 : 10)
        .frame(minHeight: 44)
        .contentShape(Rectangle())
    }
}

// MARK: - Oficina en lista

struct OficinaListaVista: View {
    @Environment(ModeloApp.self) private var modelo
    @Binding var modo: ModoOficina
    @State private var cuenta: Cuenta = .todas

    var body: some View {
        let agentes = Logica.filtrar(modelo.agentes, cuenta: cuenta, ahora: modelo.ahora)
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                EncabezadoOficina(modo: $modo, agentes: agentes)
                Picker("Cuenta", selection: $cuenta) {
                    ForEach(Cuenta.allCases) { Text($0.titulo).tag($0) }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 10)
                HStack { AvisoConexion() }.padding(.horizontal, 16)
                TarjetaTeEsperan(agentes: Logica.teEsperan(agentes))
                    .padding(.horizontal, 16)
                Rotulo(texto: "Agentes")
                    .padding(.horizontal, 16)
                    .padding(.top, 18)
                    .padding(.bottom, 8)
                LazyVStack(spacing: 8) {
                    ForEach(Logica.ordenLista(agentes)) { a in
                        NavigationLink(value: a.id) { FilaAgente(agente: a, ahora: modelo.ahora) }
                            .buttonStyle(.plain)
                    }
                    if modelo.estado != nil && agentes.isEmpty {
                        Text("No hay agentes en la oficina.")
                            .font(.system(size: 15))
                            .foregroundStyle(Color.texto2)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 24)
                    }
                    if modelo.estado == nil {
                        ProgressView().padding(.vertical, 24)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
        }
        .refreshable { await modelo.leerUnaVez() }
        .background(Color.fondo)
        .foregroundStyle(Color.texto)
    }
}

struct FilaAgente: View {
    var agente: Agente
    var ahora: Date

    var body: some View {
        let nombre = Logica.nombre(agente)
        let estado = Logica.estadoCorto(agente, ahora: ahora)
        let borde: Color = estado.tono == .verde || estado.tono == .gris ? .borde : estado.tono.borde
        HStack(spacing: 12) {
            Iniciales(texto: Logica.iniciales(nombre))
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline) {
                    Text(nombre).font(.system(size: 16, weight: .semibold)).lineLimit(1)
                    Spacer(minLength: 8)
                    if let c = Logica.textoCuenta(agente.agente.cuenta) {
                        Text(c).font(.system(size: 12)).foregroundStyle(Color.texto2)
                    }
                }
                Text(agente.estado.numero == 13 || agente.estado.numero == 14 ? Logica.loQuePide(agente) : Logica.detalleActual(agente))
                    .font(.system(size: 14))
                    .foregroundStyle(Color.texto3)
                    .lineLimit(1)
                Text(estado.texto)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(estado.tono.color)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color.white, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(borde))
        .foregroundStyle(Color.texto)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}
