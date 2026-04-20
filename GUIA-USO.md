# 🔨 Guía completa de Prompt Forge

> Aprende a exprimir Prompt Forge al 100%, de básico a avanzado.

---

## Nivel 0 — Mentalidad correcta

Antes de los comandos, entiende **qué es** Prompt Forge:

- **No es una IA.** Es un compilador determinista que traduce tu lenguaje natural ("ayudame con esto") a un prompt XML estructurado de nivel experto.
- **El trabajo fino lo hace el LLM** (Claude, GPT, Gemini) al que le pegas el prompt compilado.
- **La magia** está en que genera automáticamente: rol experto, criterios de éxito, constraints, anti-patterns, técnicas de prompting (Chain of Thought, Self-Critique, etc.) — cosas que manualmente tardarías 10 minutos en escribir.

**Regla mental:** escribe crudo, obtén estructura. No trates de "escribir bonito" tu petición — entre más natural y específica, mejor lee el compilador.

---

## Nivel 1 — Lo esencial (80% del uso)

### Los 4 comandos que usarás todos los días

```cmd
forge compile "tu petición"       :: compila a XML
forge run "tu petición"           :: compila Y ejecuta
forge doctor                       :: ¿qué puede correr mi máquina?
forge runners                      :: ¿qué tengo configurado?
```

### Tu primer flujo completo

```cmd
:: 1. Diagnóstico inicial (solo la primera vez)
forge doctor

:: 2. Configurar al menos un runner cloud (ver Nivel 2)

:: 3. Uso normal
forge run "arregla el bug en mi código que no parsea fechas correctamente"
```

### Los 3 parámetros que cambian el juego

| Parámetro | Para qué sirve | Ejemplo |
|-----------|----------------|---------|
| `--format` | Guarda en MD/HTML/TXT/PDF en vez de XML | `forge compile "..." --format md` |
| `--copy` | Copia el resultado al portapapeles | `forge run "..." --copy` |
| `-o ruta` | Guarda en una ruta específica | `forge compile "..." -o C:\docs\prompt.md` |

### Input crudo que entiende el compilador

Prompt Forge **limpia tu input automáticamente**, así que puedes:

```cmd
:: Con typos
forge compile "ayudame a haser un scraper porfa"

:: Con filler conversacional
forge compile "oye entonces necesito que me explikes como funcionan los decorators en python gracias"

:: En cualquier idioma (ES/EN/PL/FR — mezclados también funciona)
forge compile "help me refactor mi código spaghetti"
```

Internamente: detecta typos → los corrige → detecta dominio (code/writing/analysis/etc) → detecta complejidad (L1-L4) → construye el prompt.

---

## Nivel 2 — Configurar los runners (para `forge run`)

`forge compile` funciona siempre sin configuración, pero `forge run` necesita al menos **un runner**. Setea las variables de entorno **UNA VEZ** y olvídate.

### Orden de prioridad recomendado (del mejor al respaldo)

**1. GEMINI** — mejor calidad gratis
- Obtén key en: https://aistudio.google.com
- Límites: 100 requests/día (Pro), 250/día (Flash)

**2. GROQ** — el más rápido, comercial OK
- Obtén key en: https://console.groq.com
- Límites: 30 req/min, 14,400/día, no entrenan con tus inputs

**3. CEREBRAS** — 1M tokens/día, 8K contexto máx
- Obtén key en: https://cloud.cerebras.ai
- Comercial OK, sin entrenar con inputs

### Configurar las keys en Windows

```powershell
:: En PowerShell como admin, una sola vez:
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY","TU_KEY","User")
[Environment]::SetEnvironmentVariable("GROQ_API_KEY","TU_KEY","User")
[Environment]::SetEnvironmentVariable("CEREBRAS_API_KEY","TU_KEY","User")

:: Cierra y reabre la terminal. Verifica:
forge runners
```

### Cuándo usar cada uno

```cmd
forge run "..." --runner gemini      :: calidad máxima, análisis profundo
forge run "..." --runner groq        :: código iterativo, respuesta instantánea
forge run "..." --runner cerebras    :: batch: traducir mucho, resumir en volumen
forge run "..." --runner ollama      :: offline / datos sensibles
forge run "..."                      :: auto (usa el primero disponible)
```

### Estrategia por tipo de tarea

| Necesitas... | Usa |
|--------------|-----|
| Escribir un correo/artículo/análisis | **Gemini** |
| Código que hay que iterar rápido | **Groq** |
| Traducir 500 productos de MercadoLibre | **Cerebras** |
| Datos de clientes privados | **Ollama local** |
| Algo sin internet | **Ollama local** |
| Lo que sea, el primero que funcione | **auto** |

---

## Nivel 3 — Forzar el comportamiento del compilador

El compilador detecta automáticamente, pero a veces se equivoca. Tienes dos palancas:

### Forzar dominio

Si tu petición es ambigua:

```cmd
:: El compilador puede pensar que "BJJ" es analysis en vez de writing
forge compile "artículo sobre BJJ" --domain writing

:: Forzar que lo trate como código aunque no mencione lenguaje
forge compile "refactoriza esto" --domain code
```

**Opciones disponibles:** `code`, `writing`, `analysis`, `creative`, `research`, `personal`, `other`

### Forzar nivel de complejidad

Cuatro niveles:

- **L1** — trivial (1-3 líneas en la respuesta final)
- **L2** — estándar
- **L3** — multi-parte con reasoning explícito
- **L4** — arquitectura/estrategia con self-critique hostil

```cmd
:: Pregunta corta pero quieres análisis profundo
forge compile "¿qué es recursion?" --level 4

:: Tarea que parece compleja pero solo quieres respuesta directa
forge compile "diseña un sistema de..." --level 2
```

### Combinarlos

```cmd
forge compile "tu petición" --domain analysis --level 4 --format md --copy
```

---

## Nivel 4 — Flujos de trabajo reales

### Flujo 1: Análisis técnico (como el caso de la acción VT)

```cmd
forge compile "analisis tecnico de la accion VT, dame senal de compra con indicadores" --domain analysis --level 3 --format md --copy
```

Pegas en Gemini 2.5 Pro (que conecta a internet) → obtienes análisis real con datos actualizados.

### Flujo 2: Refactor de código existente

```cmd
:: 1. Guarda tu código en un .txt
:: 2. Pasa descripción + archivo
type mi_codigo.py | forge compile -f - --domain code --level 3
```

O más directo:

```cmd
forge run "revisa el archivo adjunto y sugiere refactor: [pega código aquí]" --runner groq --copy
```

### Flujo 3: Escribir en batch

Para generar 10 prompts distintos rápido:

```cmd
forge compile "variante A de email" --format md -o emails\a.md
forge compile "variante B de email" --format md -o emails\b.md
forge compile "variante C de email" --format md -o emails\c.md
```

O usando un archivo con múltiples peticiones (una por línea):

```powershell
Get-Content peticiones.txt | ForEach-Object { forge compile $_ --format md }
```

### Flujo 4: Pipeline con otro comando

```cmd
:: Solo XML, sin ruido — ideal para pipear
forge compile "..." --raw > prompt.xml

:: En PowerShell, enviarlo directo al portapapeles
forge compile "..." --raw | Set-Clipboard
```

---

## Nivel 5 — Las features ocultas

### La interfaz web

```cmd
forge web
```

Abre tu navegador con interfaz dark-mode. Útil cuando:

- No quieres estar tocando CLI
- Vas a hacer muchas compilaciones seguidas
- Quieres enseñarle el script a alguien

**Atajo:** dentro del textarea, `Ctrl+Enter` = compilar y ejecutar.

### El doctor

```cmd
forge doctor
```

Te dice exactamente:

- Cuánta RAM/CPU/VRAM/disco tienes
- Si hay internet
- Qué runner te conviene
- Si vas a Ollama, qué modelo específico descargar

**Úsalo cuando:**

- Cambies de computadora
- Quieras saber qué modelo local correr (te dice el exacto según tu RAM libre)
- Algo no funciona y quieres debug rápido

### Base de conocimiento creciente

El compilador tiene 12 técnicas de prompting seed (CoT, Few-Shot, Self-Critique, etc.). Puedes hacer que aprenda más scrapeando internet:

```cmd
forge learn
```

Descarga técnicas de DAIR-AI, OpenAI Cookbook, PromptingGuide, etc. Después de esto, tus compilaciones futuras inyectarán técnicas más variadas.

Añade tus propias fuentes en `data\sources.yaml`:

```yaml
sources:
  - url: https://tu-blog-favorito.com/prompting-techniques
    domains: [writing, any]
```

### Feedback loop — el script aprende de ti

Después de cada compilación, si te gustó el resultado:

```cmd
forge rate 5 --note "perfecto para mi caso"
```

Si estuvo mal:

```cmd
forge rate 2 --note "demasiado verbose"
```

Esto ajusta los pesos de las técnicas que fueron inyectadas en esa compilación. **Con el tiempo, las técnicas que funcionan para TI aparecen más seguido**, las que no, menos.

Ver tu uso:

```cmd
forge stats
```

Muestra: total de compilaciones, rating promedio, top técnicas, distribución por dominio/nivel.

### Uso desde Google Colab (100% online)

Abre `colab/prompt-forge-colab.ipynb` en https://colab.research.google.com y corre `Runtime → Run all`. Todo corre en servidores gratis de Google — no ocupa nada de tu Dell.

---

## Nivel 6 — Técnicas avanzadas

### 1. Usar un prompt como "system prompt" permanente

Compilas una vez, guardas el XML, y lo pegas al inicio de cada conversación con Claude:

```cmd
forge compile "eres mi asistente de desarrollo de DiscordForge, conoces Next.js/Prisma/Discord.js v14, siempre respondes en español con código comentado" --domain code --level 3 -o system-prompt-discordforge.xml
```

Copia ese XML → úsalo como "Instrucciones personalizadas" en Claude/ChatGPT, o como `CLAUDE.md` en Claude Code.

### 2. Chaining: output de un LLM → nuevo prompt

```cmd
:: 1. Ejecuta la primera petición y guarda la respuesta
forge run "dame 10 ideas de features para discordforge" --format md -o ideas.md

:: 2. Pasa la respuesta como input al siguiente prompt
forge compile "evalúa estas ideas y rankealas por ROI: $(type ideas.md)" --level 4
```

### 3. Archivos como input

```cmd
:: Lee una petición larga desde archivo
forge compile -f briefing-cliente.txt --level 4

:: O desde stdin
type briefing.txt | forge compile --level 4
```

### 4. Prompts para ti mismo (plantillas reutilizables)

Crea "macros" guardando XMLs que usas seguido:

```
C:\Users\DELL\Documents\forge-templates\
  review-codigo.xml      (compilado de "hazme code review estricto en TypeScript")
  escribir-docs.xml      (compilado de "documenta este módulo para otro dev")
  debug-lento.xml        (compilado de "ayudame a diagnosticar por qué es lento")
```

Cuando los necesites: abre el `.xml`, copia, pega en Claude, agrega el código/contexto específico al final.

### 5. Integración con tu workflow de DiscordForge

Ejemplos prácticos para tu proyecto real:

```cmd
:: Generar descripción de servidor para Discord Forge
forge run "escribe una descripción marketing para un servidor de Discord de anime, tono casual, 150 palabras, incluye CTA para invitar amigos" --runner groq --format md --copy

:: Code review de tu admin panel
forge run "revisa este endpoint de Next.js y sugiere mejoras de seguridad: [pega código]" --runner gemini --level 3

:: Script para TikTok @getforged
forge run "guion para TikTok 30 segundos sobre por qué nuestro server listing es mejor que top.gg, tono millennial, sin sonar defensivo" --runner gemini --format md -o tiktok-script.md
```

---

## Nivel 7 — Debugging y troubleshooting

### "No runners available"

```cmd
:: Verificar que las vars están seteadas
echo %GEMINI_API_KEY%
echo %GROQ_API_KEY%

:: Si están vacías, re-setéalas con setx para que persistan:
setx GEMINI_API_KEY "tu_key"
:: CIERRA la terminal y vuelve a abrir
```

### El compilador detectó mal el dominio

Usa `--domain` explícito. El detector es heurístico, no perfecto.

### El resultado es demasiado largo/corto

Usa `--level`. L1 = muy corto, L4 = extensivo.

### Error de rate limit en Gemini

100 RPD free tier. Cambia temporalmente a otro runner:

```cmd
forge run "..." --runner groq
```

### El XML se ve raro en el navegador

Los XMLs están diseñados para **pegarse en LLMs**, no para abrirse en el navegador (aunque ahora son válidos XML). Si quieres leerlo, usa `--format md` o `--format html`.

### Verificar que todo funciona

```cmd
run_tests.bat
```

45 tests deberían pasar. Si alguno falla, algo se rompió en tu instalación.

---

## Nivel 8 — Mini-recetario de comandos listos

Copia-pega estos cuando los necesites:

```cmd
:: Rápida respuesta a pregunta general
forge run "tu pregunta" --copy

:: Prompt para pegar en Claude manualmente, bonito en markdown
forge compile "tu petición" --format md --copy

:: Código complejo, respuesta estructurada
forge run "tu petición de código" --domain code --level 4 --runner gemini --format md

:: Batch de escritura, guardado en carpeta
forge compile "variante email formal" --format md -o emails\formal.md
forge compile "variante email casual" --format md -o emails\casual.md

:: Analizar algo privado con Ollama local
forge run "tu petición con datos confidenciales" --runner ollama --no-save

:: Toda la info de tu setup
forge doctor && forge runners && forge stats

:: Interfaz web en vez de CLI
forge web

:: Aprender técnicas nuevas de internet
forge learn && forge stats
```

---

## Cheatsheet de 30 segundos

```
ENTRADA      → forge compile / forge run
FORMATO      → --format [xml|md|txt|html|pdf]
PORTAPAPELES → --copy
RUNNER       → --runner [auto|gemini|groq|cerebras|ollama]
DOMINIO      → --domain [code|writing|analysis|creative|research|personal]
COMPLEJIDAD  → --level [1|2|3|4]
ARCHIVO      → -f archivo.txt  /  -o ruta\salida.md
SIN GUARDAR  → --no-save
SOLO XML     → --raw
```

---

## Dónde se guarda todo

- **Outputs automáticos:** `C:\Users\DELL\prompt-forge-outputs\`
- **Base de datos** (historial, ratings, técnicas): `C:\Users\DELL\.prompt-forge\forge.db`
- **Config de runners:** variables de entorno de Windows (User scope)
- **Fuentes de aprendizaje:** `data\sources.yaml` (edítalo para añadir URLs)

---

## El principio que resume todo

**Prompt Forge te quita el trabajo de escribir prompts estructurados, para que te concentres en pensar qué necesitas.** Escribes la petición como te salga, eliges el runner según la tarea, y obtienes una respuesta de calidad profesional. Todo lo demás — el rol experto, los constraints, las técnicas, el formato, el guardado — lo hace el script.

Cuando ya domines esto, el cuello de botella deja de ser "cómo le pido bien al LLM" y pasa a ser "qué quiero hacer hoy". Que es como debería ser.
