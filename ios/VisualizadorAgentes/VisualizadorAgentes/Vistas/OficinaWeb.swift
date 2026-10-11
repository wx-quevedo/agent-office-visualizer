import SwiftUI
import WebKit

/// La oficina 3D de la web (/oficina/3d?app=ios) en un WKWebView con la
/// sesión de la app. La web avisa del agente tocado por el manejador "oficina".
/// Un solo WKWebView para toda la app: pasar de Lista a 3D no recarga la escena.
@MainActor
final class OficinaWeb: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
    private static var actual: OficinaWeb?

    let vista: WKWebView
    let credencial: Credencial
    var alTocarAgente: (String) -> Void = { _ in }
    var alPerderSesion: () -> Void = {}
    private var cargada = false

    static func compartida(_ c: Credencial) -> OficinaWeb {
        if let a = actual, a.credencial == c { return a }
        let nueva = OficinaWeb(credencial: c)
        actual = nueva
        return nueva
    }

    /// Al salir: la vista y sus cookies se olvidan.
    static func olvidar() {
        actual = nil
        let tienda = WKWebsiteDataStore.default()
        tienda.removeData(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(), modifiedSince: .distantPast) {}
    }

    private init(credencial: Credencial) {
        self.credencial = credencial
        let conf = WKWebViewConfiguration()
        conf.websiteDataStore = .default()
        conf.allowsInlineMediaPlayback = true
        vista = WKWebView(frame: .zero, configuration: conf)
        super.init()
        conf.userContentController.add(Debil(self), name: "oficina")
        // La app tiene su propia pestaña "Dónde quedamos": se marca la visita
        // para que la web no salte allí (regla de las 8 horas), también con una
        // web que todavía no conoce ?app=ios.
        conf.userContentController.addUserScript(WKUserScript(
            source: "try { localStorage.setItem('oficina-ultima-visita', String(Date.now())) } catch (e) {}",
            injectionTime: .atDocumentStart, forMainFrameOnly: true))
        vista.navigationDelegate = self
        vista.isOpaque = false
        vista.backgroundColor = UIColor(Color.fondo3D)
        vista.scrollView.backgroundColor = UIColor(Color.fondo3D)
        vista.scrollView.isScrollEnabled = false
        vista.scrollView.bounces = false
        vista.scrollView.contentInsetAdjustmentBehavior = .never
        vista.allowsBackForwardNavigationGestures = false
        vista.isInspectable = true
    }

    static func urlOficina(_ servidor: URL) -> URL {
        URL(string: servidor.absoluteString + "/oficina/3d?app=ios")!
    }

    func cargarSiHaceFalta() {
        guard !cargada else { return }
        cargada = true
        let url = Self.urlOficina(credencial.servidor)
        guard let cookie = credencial.cookie() else {
            vista.load(URLRequest(url: url))
            return
        }
        vista.configuration.websiteDataStore.httpCookieStore.setCookie(cookie) { [weak self] in
            self?.vista.load(URLRequest(url: url))
        }
    }

    func recargar() {
        cargada = false
        cargarSiHaceFalta()
    }

    // MARK: - WKScriptMessageHandler

    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        guard let cuerpo = m.body as? [String: Any], let tipo = cuerpo["tipo"] as? String else { return }
        if tipo == "agente", let id = cuerpo["id"] as? String, !id.isEmpty { alTocarAgente(id) }
    }

    // MARK: - WKNavigationDelegate

    func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction) async -> WKNavigationActionPolicy {
        guard let url = a.request.url else { return .cancel }
        // Sin sesión la web manda a /entrar: la app vuelve a su propia pantalla Entrar.
        if url.host() == credencial.servidor.host(), url.path().hasPrefix("/entrar") {
            alPerderSesion()
            return .cancel
        }
        // Enlaces a otros sitios: fuera de la app.
        if url.host() != credencial.servidor.host(), a.navigationType == .linkActivated {
            await UIApplication.shared.open(url)
            return .cancel
        }
        return .allow
    }

    func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) { cargada = false }
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { cargada = false }
    func webViewWebContentProcessDidTerminate(_ w: WKWebView) { recargar() }

    /// El manejador de mensajes retiene a su objeto: se pasa uno débil.
    private final class Debil: NSObject, WKScriptMessageHandler {
        weak var destino: OficinaWeb?
        init(_ d: OficinaWeb) { destino = d }
        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
            MainActor.assumeIsolated { destino?.userContentController(c, didReceive: m) }
        }
    }
}

struct OficinaWebVista: UIViewRepresentable {
    let web: OficinaWeb

    func makeUIView(context: Context) -> WKWebView {
        web.cargarSiHaceFalta()
        return web.vista
    }

    func updateUIView(_ v: WKWebView, context: Context) {}
}

/// Una página de la web con la sesión de la app (Historial).
struct PaginaWeb: UIViewRepresentable {
    let url: URL
    let credencial: Credencial

    func makeUIView(context: Context) -> WKWebView {
        let conf = WKWebViewConfiguration()
        conf.websiteDataStore = .default()
        let v = WKWebView(frame: .zero, configuration: conf)
        v.backgroundColor = .white
        if let c = credencial.cookie() {
            conf.websiteDataStore.httpCookieStore.setCookie(c) { v.load(URLRequest(url: url)) }
        } else {
            v.load(URLRequest(url: url))
        }
        return v
    }

    func updateUIView(_ v: WKWebView, context: Context) {}
}
