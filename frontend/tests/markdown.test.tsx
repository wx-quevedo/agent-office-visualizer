import { GlobalRegistrator } from "@happy-dom/global-registrator";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  enlaceSeguro,
  inline,
  parsearMarkdown,
  type Bloque,
} from "@/components/proyectos/logicaMarkdown";

let React: typeof import("react");
let ReactDOM: typeof import("react-dom/client");
let Markdown: typeof import("@/components/proyectos/Markdown").Markdown;
let ChatVista: typeof import("@/components/proyectos/Chat").ChatVista;

beforeAll(async () => {
  GlobalRegistrator.register({ url: "http://localhost:3100/proyectos" });
  (
    globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  React = await import("react");
  ReactDOM = await import("react-dom/client");
  Markdown = (await import("@/components/proyectos/Markdown")).Markdown;
  ChatVista = (await import("@/components/proyectos/Chat")).ChatVista;
});

afterAll(async () => {
  await GlobalRegistrator.unregister();
});

afterEach(() => {
  document.body.innerHTML = "";
});

async function montar(texto: string): Promise<HTMLElement> {
  const el = document.createElement("div");
  document.body.appendChild(el);
  const raiz = ReactDOM.createRoot(el);
  await React.act(async () => {
    raiz.render(React.createElement(Markdown, { texto }));
  });
  return el;
}

/** Nothing executable in the rendered DOM; every link is http(s)/mailto. */
function sinPeligro(el: HTMLElement) {
  expect(
    el.querySelector("script, img, iframe, object, embed, svg"),
  ).toBeNull();
  for (const n of el.querySelectorAll("*")) {
    for (const a of n.getAttributeNames()) {
      expect(a.toLowerCase().startsWith("on")).toBe(false);
    }
  }
  for (const a of el.querySelectorAll("a")) {
    expect(a.getAttribute("href") ?? "").toMatch(/^(https?:\/\/|mailto:)/);
    expect(a.getAttribute("target")).toBe("_blank");
    expect(a.getAttribute("rel")).toBe("noopener noreferrer");
  }
}

function parrafo(texto: string) {
  const b = parsearMarkdown(texto);
  expect(b).toHaveLength(1);
  expect(b[0].tipo).toBe("parrafo");
  return (b[0] as Extract<Bloque, { tipo: "parrafo" }>).hijos;
}

describe("enlaceSeguro", () => {
  it("acepta http, https y mailto", () => {
    expect(enlaceSeguro("https://ejemplo.com/a?b=1")).toBe(
      "https://ejemplo.com/a?b=1",
    );
    expect(enlaceSeguro("HTTP://Ejemplo.com")).toBe("http://ejemplo.com/");
    expect(enlaceSeguro("mailto:hola@ejemplo.com")).toBe(
      "mailto:hola@ejemplo.com",
    );
  });

  it("rechaza otros esquemas, relativas y espacios raros", () => {
    for (const u of [
      "javascript:alert(1)",
      "JaVaScRiPt:alert(1)",
      " javascript:alert(1)",
      "java\tscript:alert(1)",
      "java\nscript:alert(1)",
      "\u0001javascript:alert(1)",
      "data:text/html,<script>alert(1)</script>",
      "vbscript:msgbox(1)",
      "file:///etc/passwd",
      "/ruta/relativa",
      "ejemplo.com",
      "https://",
      "",
    ])
      expect(enlaceSeguro(u)).toBeNull();
  });
});

describe("parser de markdown", () => {
  it("párrafos separados por línea en blanco y saltos de línea", () => {
    const b = parsearMarkdown("uno\ndos\n\ntres");
    expect(b).toEqual([
      {
        tipo: "parrafo",
        hijos: [
          { tipo: "texto", texto: "uno" },
          { tipo: "salto" },
          { tipo: "texto", texto: "dos" },
        ],
      },
      { tipo: "parrafo", hijos: [{ tipo: "texto", texto: "tres" }] },
    ]);
    expect(parsearMarkdown("a\r\n\r\nb")).toHaveLength(2);
  });

  it("negrita con ** y __, cursiva con * y _", () => {
    expect(inline("**a** y __b__")).toEqual([
      { tipo: "negrita", hijos: [{ tipo: "texto", texto: "a" }] },
      { tipo: "texto", texto: " y " },
      { tipo: "negrita", hijos: [{ tipo: "texto", texto: "b" }] },
    ]);
    expect(inline("*a* y _b_")).toEqual([
      { tipo: "cursiva", hijos: [{ tipo: "texto", texto: "a" }] },
      { tipo: "texto", texto: " y " },
      { tipo: "cursiva", hijos: [{ tipo: "texto", texto: "b" }] },
    ]);
    expect(inline("***ambas***")).toEqual([
      {
        tipo: "negrita",
        hijos: [
          { tipo: "cursiva", hijos: [{ tipo: "texto", texto: "ambas" }] },
        ],
      },
    ]);
  });

  it("no rompe palabras con guion bajo ni asteriscos sueltos", () => {
    expect(inline("edita nombre_de_archivo_final.py y mi_var")).toEqual([
      { tipo: "texto", texto: "edita nombre_de_archivo_final.py y mi_var" },
    ]);
    expect(inline("2 * 3 * 4 y a ** b")).toEqual([
      { tipo: "texto", texto: "2 * 3 * 4 y a ** b" },
    ]);
    expect(inline("**sin cerrar")).toEqual([
      { tipo: "texto", texto: "**sin cerrar" },
    ]);
    expect(inline("\\*literal\\*")).toEqual([
      { tipo: "texto", texto: "*literal*" },
    ]);
  });

  it("código en línea sin interpretar lo de adentro", () => {
    expect(inline("usa `a_b **c** <b>` ya")).toEqual([
      { tipo: "texto", texto: "usa " },
      { tipo: "codigo", texto: "a_b **c** <b>" },
      { tipo: "texto", texto: " ya" },
    ]);
    expect(inline("`` con ` adentro ``")).toEqual([
      { tipo: "codigo", texto: "con ` adentro" },
    ]);
  });

  it("bloques de código con y sin lenguaje, conservando espacios", () => {
    const b = parsearMarkdown(
      "antes\n```ts\nconst a = 1;\n\n    if (a) {  }\n```\n```\n**no** _md_\n```",
    );
    expect(b[1]).toEqual({
      tipo: "codigo",
      lenguaje: "ts",
      texto: "const a = 1;\n\n    if (a) {  }",
    });
    expect(b[2]).toEqual({
      tipo: "codigo",
      lenguaje: null,
      texto: "**no** _md_",
    });
    // unclosed: until the end
    expect(parsearMarkdown("```\nabierto")[0]).toEqual({
      tipo: "codigo",
      lenguaje: null,
      texto: "abierto",
    });
  });

  it("listas con -, * y numeradas, con anidadas por sangría", () => {
    const b = parsearMarkdown(
      "- uno\n* dos\n  - dos.a\n  - dos.b\n\n3. tres\n4. cuatro\n   1. cuatro.uno",
    );
    expect(b).toHaveLength(2);
    const [ul, ol] = b as Extract<Bloque, { tipo: "lista" }>[];
    expect(ul.ordenada).toBe(false);
    expect(ul.items).toHaveLength(2);
    const anidada = ul.items[1].bloques[1] as Extract<
      Bloque,
      { tipo: "lista" }
    >;
    expect(anidada.tipo).toBe("lista");
    expect(anidada.items).toHaveLength(2);
    expect(ol.ordenada).toBe(true);
    expect(ol.inicio).toBe(3);
    expect(ol.items).toHaveLength(2);
    expect(ol.items[1].bloques[1].tipo).toBe("lista");
  });

  it("anidada con dos espacios bajo un número y continuación perezosa", () => {
    const [ol] = parsearMarkdown(
      "1. primero\n  - detalle\n2. segundo\nsigue el segundo",
    ) as Extract<Bloque, { tipo: "lista" }>[];
    expect(ol.items).toHaveLength(2);
    expect(ol.items[0].bloques[1].tipo).toBe("lista");
    expect(ol.items[1].bloques).toEqual([
      {
        tipo: "parrafo",
        hijos: [
          { tipo: "texto", texto: "segundo" },
          { tipo: "salto" },
          { tipo: "texto", texto: "sigue el segundo" },
        ],
      },
    ]);
  });

  it("encabezados # a ### (más se quedan en el nivel 3)", () => {
    const b = parsearMarkdown("# Uno\n## Dos\n### Tres\n#### Cuatro\n#nada");
    expect(
      b.slice(0, 4).map((x) => x.tipo === "encabezado" && x.nivel),
    ).toEqual([1, 2, 3, 3]);
    expect(b[4].tipo).toBe("parrafo");
  });

  it("citas con >, separador y párrafo que sigue", () => {
    const b = parsearMarkdown("> **ojo**\n> sigue\n\n---\nfin");
    expect(b[0].tipo).toBe("cita");
    const cita = b[0] as Extract<Bloque, { tipo: "cita" }>;
    expect(cita.bloques[0].tipo).toBe("parrafo");
    expect(b[1]).toEqual({ tipo: "separador" });
    expect(b[2].tipo).toBe("parrafo");
  });

  it("enlaces [texto](url), con título, URLs sueltas y <url>", () => {
    expect(inline('[Docs](https://ejemplo.com/a_(b) "título")')).toEqual([
      {
        tipo: "enlace",
        url: "https://ejemplo.com/a_(b)",
        hijos: [{ tipo: "texto", texto: "Docs" }],
      },
    ]);
    expect(inline("ver https://ejemplo.com/x_y. Y (https://e.com/z).")).toEqual(
      [
        { tipo: "texto", texto: "ver " },
        {
          tipo: "enlace",
          url: "https://ejemplo.com/x_y",
          hijos: [{ tipo: "texto", texto: "https://ejemplo.com/x_y" }],
        },
        { tipo: "texto", texto: ". Y (" },
        {
          tipo: "enlace",
          url: "https://e.com/z",
          hijos: [{ tipo: "texto", texto: "https://e.com/z" }],
        },
        { tipo: "texto", texto: ")." },
      ],
    );
    expect(inline("<mailto:a@b.com>")).toEqual([
      {
        tipo: "enlace",
        url: "mailto:a@b.com",
        hijos: [{ tipo: "texto", texto: "mailto:a@b.com" }],
      },
    ]);
  });

  it("imágenes: enlace normal si la URL es válida, si no texto", () => {
    expect(inline("![logo](https://e.com/l.png)")).toEqual([
      {
        tipo: "enlace",
        url: "https://e.com/l.png",
        hijos: [{ tipo: "texto", texto: "logo" }],
      },
    ]);
    expect(inline("![x](data:image/png;base64,AAAA)")).toEqual([
      { tipo: "texto", texto: "![x](data:image/png;base64,AAAA)" },
    ]);
  });

  it("enlaces con esquema no permitido quedan como texto literal", () => {
    for (const t of [
      "[x](javascript:alert(1))",
      "[x](JaVaScRiPt:alert(1))",
      "[x](data:text/html,<script>alert(1)</script>)",
      "[x](vbscript:msgbox(1))",
    ])
      expect(parrafo(t)).toEqual([{ tipo: "texto", texto: t }]);
  });
});

describe("componente Markdown", () => {
  it("cada elemento soportado como elemento de React", async () => {
    const el = await montar(
      [
        "# Título",
        "Texto con **negrita**, _cursiva_ y `codigo`.",
        "",
        "- a",
        "  - a.1",
        "",
        "2. dos",
        "3. tres",
        "",
        "> cita",
        "",
        "```bash",
        "  npm   install",
        "```",
        "",
        "[sitio](https://ejemplo.com) y https://otro.com",
      ].join("\n"),
    );
    expect(el.querySelector("p strong")?.textContent).toBe("Título");
    expect(el.querySelector("h1, h2, h3")).toBeNull();
    expect(el.firstElementChild?.firstElementChild?.textContent).toBe("Título");
    expect(el.querySelectorAll("strong")[1].textContent).toBe("negrita");
    expect(el.querySelector("em")?.textContent).toBe("cursiva");
    expect(el.querySelector("p > code")?.textContent).toBe("codigo");
    expect(el.querySelector("ul li ul li")?.textContent).toBe("a.1");
    const ol = el.querySelector("ol")!;
    expect(ol.getAttribute("start")).toBe("2");
    expect(ol.querySelectorAll("li")).toHaveLength(2);
    expect(el.querySelector("blockquote")?.textContent).toBe("cita");
    const pre = el.querySelector("pre")!;
    expect(pre.querySelector("code")?.textContent).toBe("  npm   install");
    expect(pre.getAttribute("data-lenguaje")).toBe("bash");
    const enlaces = [...el.querySelectorAll("a")];
    expect(enlaces.map((a) => a.getAttribute("href"))).toEqual([
      "https://ejemplo.com/",
      "https://otro.com/",
    ]);
    sinPeligro(el);
  });

  it("respuesta real mezclada: negritas, lista numerada y bloque de código", async () => {
    const el = await montar(
      [
        "Listo, revisé el proyecto. **Resumen:**",
        "",
        "1. Corregí `nombre_de_archivo.ts` para que **no** falle.",
        "2. Agregué pruebas en _tests/carrito.test.ts_.",
        "3. Falta revisar el despliegue:",
        "",
        "```ts",
        "export const total = (xs: number[]) =>",
        "  xs.reduce((a, b) => a + b, 0);",
        "```",
        "",
        "Más detalles en https://ejemplo.com/pr/12.",
      ].join("\n"),
    );
    const items = el.querySelectorAll("ol > li");
    expect(items).toHaveLength(3);
    expect(items[0].querySelector("code")?.textContent).toBe(
      "nombre_de_archivo.ts",
    );
    expect(items[0].querySelector("strong")?.textContent).toBe("no");
    expect(items[1].querySelector("em")?.textContent).toBe(
      "tests/carrito.test.ts",
    );
    expect(el.querySelector("pre code")?.textContent).toBe(
      "export const total = (xs: number[]) =>\n  xs.reduce((a, b) => a + b, 0);",
    );
    expect(el.querySelector("a")?.getAttribute("href")).toBe(
      "https://ejemplo.com/pr/12",
    );
    expect(el.textContent).not.toContain("**");
    sinPeligro(el);
  });

  it("la burbuja del orquestador usa markdown y la de Washington no", async () => {
    const el = document.createElement("div");
    document.body.appendChild(el);
    const raiz = ReactDOM.createRoot(el);
    await React.act(async () => {
      raiz.render(
        React.createElement(ChatVista, {
          proyecto: { id: "p1", estado: "activo" },
          chat: {
            mensajes: [
              {
                id: "1",
                autor: "washington",
                texto: "**hola**\nsegunda línea",
                creado: "2026-10-11T15:00:00Z",
              },
              {
                id: "2",
                autor: "orquestador",
                texto: "**hola**\n- uno",
                creado: "2026-10-11T15:01:00Z",
              },
            ],
            ordenes: [],
          },
          ahora: Date.parse("2026-10-11T16:00:00Z"),
        }),
      );
    });
    const [mia, orq] = [...el.querySelector('[role="log"]')!.children];
    expect(mia.querySelector("strong")).toBeNull();
    expect(mia.textContent).toContain("**hola**\nsegunda línea");
    expect(orq.querySelector("strong")?.textContent).toBe("hola");
    expect(orq.querySelector("ul li")?.textContent).toBe("uno");
  });
});

describe("seguridad del markdown", () => {
  // Each case also carries a markdown link with a forbidden scheme, so every
  // test fails if the scheme check of enlaceSeguro is removed.
  const casos: [string, string, string[]][] = [
    [
      "etiqueta script",
      "<script>alert(1)</script> [x](javascript:alert(1))",
      ["<script>alert(1)</script>", "[x](javascript:alert(1))"],
    ],
    [
      "img con onerror",
      "<img src=x onerror=alert(1)> y [y](javascript:alert(2))",
      ["<img src=x onerror=alert(1)>", "[y](javascript:alert(2))"],
    ],
    [
      "enlace javascript:",
      "**ojo** [x](javascript:alert(1))",
      ["[x](javascript:alert(1))"],
    ],
    [
      "enlace JaVaScRiPt: con mayúsculas",
      "[x](JaVaScRiPt:alert(1))",
      ["[x](JaVaScRiPt:alert(1))"],
    ],
    [
      "enlace data:",
      "[x](data:text/html,<script>alert(1)</script>)",
      ["[x](data:text/html,<script>alert(1)</script>)"],
    ],
    [
      "enlace vbscript: e imagen data:",
      "[x](vbscript:msgbox(1)) ![i](data:image/svg+xml,<svg onload=alert(1)>)",
      [
        "[x](vbscript:msgbox(1))",
        "![i](data:image/svg+xml,<svg onload=alert(1)>)",
      ],
    ],
    [
      "comillas que intentan salir del atributo",
      '[x](javascript:alert(1)"onmouseover="alert(2)) [y](<javascript:alert(3)>)',
      [
        '[x](javascript:alert(1)"onmouseover="alert(2))',
        "[y](<javascript:alert(3)>)",
      ],
    ],
    [
      "espacios y controles raros en el esquema",
      "[x]( javascript:alert(1) ) [y](<java\tscript:alert(2)>) [z](<\u0001javascript:alert(3)>)",
      ["[x]( javascript:alert(1) )", "[y](<java\tscript:alert(2)>)"],
    ],
    [
      "HTML en enlace y en bloque de código",
      '<a href="javascript:alert(1)">a</a>\n```\n<script>alert(1)</script>\n```\n[x](javascript:void(0))',
      [
        '<a href="javascript:alert(1)">a</a>',
        "<script>alert(1)</script>",
        "[x](javascript:void(0))",
      ],
    ],
  ];

  for (const [nombre, texto, literales] of casos) {
    it(nombre, async () => {
      const el = await montar(texto);
      sinPeligro(el);
      expect(el.querySelectorAll("a")).toHaveLength(0);
      for (const l of literales) expect(el.textContent).toContain(l);
    });
  }

  it("un enlace válido con comillas queda escapado dentro del href", async () => {
    const el = await montar('[x](https://e.com/a"onclick="alert(1))');
    sinPeligro(el);
    const a = el.querySelector("a")!;
    expect(a.getAttribute("href")).toBe(
      "https://e.com/a%22onclick=%22alert(1)",
    );
    expect(a.getAttribute("onclick")).toBeNull();
  });
});
