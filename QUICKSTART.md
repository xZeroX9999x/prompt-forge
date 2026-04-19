# Guía de inicio rápido (Dell Windows, 32GB RAM, gráficos integrados)

Esta guía está escrita específicamente para tu hardware. Sigue los pasos en orden.

---

## 🌐 ¿Quieres usarlo sin instalar nada?

**Opción A — Web UI local**: Si ya instalaste Prompt Forge en tu máquina, puedes usarlo con interfaz web en tu navegador en vez de terminal:

```cmd
forge web
```

Abre automáticamente `http://127.0.0.1:7788` en tu navegador. Escribes, haces clic, listo. Mismas funciones que la CLI pero con interfaz gráfica.

**Opción B — Google Colab (100% online, cero instalación)**: Usa el notebook `colab/prompt-forge-colab.ipynb` incluido en el repo. Lo abres en https://colab.research.google.com (subiendo el `.ipynb` o abriéndolo desde GitHub), haces **Runtime → Run all**, y escribes tu petición. Todo corre en los servidores de Google. No necesitas instalar Python ni nada. Los archivos generados se pueden descargar con un clic al final.

---

## 🩺 Antes de empezar: diagnostica tu máquina

```cmd
forge doctor
```

Detecta automáticamente:
- RAM total y libre
- CPU y núcleos
- GPU y VRAM (si tienes dedicada)
- Espacio en disco
- Si hay internet

Y te recomienda exactamente **qué runner y qué modelo usar** para tu máquina específica. Ejecuta esto primero siempre.

---

## Opción 1: Solo compilar prompts (sin ejecución automática)

Si solo quieres generar prompts estructurados y pegarlos tú mismo en Claude/ChatGPT/Gemini, esto es todo lo que necesitas:

```cmd
git clone https://github.com/TU_USUARIO/prompt-forge.git
cd prompt-forge
install.bat
.venv\Scripts\activate.bat

forge compile "lo que sea que necesites"
```

Copias el XML que sale, lo pegas en Claude.ai, listo.

---

## Opción 2: Compilar + ejecutar automáticamente (recomendado)

Para que `forge run "..."` compile Y ejecute el prompt sin que tengas que copiar/pegar, necesitas al menos **uno** de estos runners configurados.

### 🏆 Tier 1: Google Gemini (la mejor calidad gratis)

1. Ve a https://aistudio.google.com → inicia sesión con tu cuenta Google
2. Click en "Get API key" → copia la clave
3. En PowerShell (admin):

```powershell
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "TU_CLAVE_AQUI", "User")
```

4. Cierra y reabre la terminal. Verifica con `forge runners`.

**Limites gratuitos (abril 2026)**: 100 requests/día en Gemini 2.5 Pro, 250/día en 2.5 Flash. Suficiente para uso personal intenso.
**Cuidado**: los inputs del tier gratuito pueden ser usados por Google para entrenar. No lo uses con datos sensibles de clientes.

### 🚀 Tier 2: Groq (el más rápido, comercial OK)

Para cuando necesites respuestas instantáneas (útil en loops de código).

1. Ve a https://console.groq.com → regístrate
2. "API Keys" → "Create API Key"
3. Configura la variable:

```powershell
[Environment]::SetEnvironmentVariable("GROQ_API_KEY", "TU_CLAVE_AQUI", "User")
```

**Límites gratuitos**: 30 requests/min, 14,400/día. Uso comercial permitido, no entrenan con tus inputs. Modelos como Llama 3.3 70B corren a 500-1000 tokens/segundo.

### 💾 Tier 3: Cerebras (1M tokens/día)

Para trabajos de volumen (traducciones, resúmenes en batch).

1. https://cloud.cerebras.ai → registro
2. Obtén la API key
3. Configura:

```powershell
[Environment]::SetEnvironmentVariable("CEREBRAS_API_KEY", "TU_CLAVE_AQUI", "User")
```

**Límite**: 8K de contexto, pero 1M tokens/día. Comercial OK, sin entrenar con inputs.

### 🔒 Tier 4: Ollama local (offline, privado)

**Investigación honesta**: con tu hardware (32GB RAM, gráficos integrados, sin GPU dedicada), Ollama correrá un modelo de 14B a ~4-7 tokens/segundo. Útil como respaldo offline o para datos sensibles, pero **no es tu driver principal**. Los tiers 1-3 serán drásticamente mejores.

Si aún lo quieres:

```cmd
winget install -e --id Ollama.Ollama
```

Una vez instalado, `forge run` lo detectará automáticamente y descargará **Qwen3-14B** (~9GB en disco, el mejor modelo local para tu perfil según la investigación) la primera vez que lo uses.

Para elegir un modelo distinto:

```powershell
[Environment]::SetEnvironmentVariable("FORGE_OLLAMA_MODEL", "llama3.1:8b", "User")
```

Alternativas recomendadas para tu hardware:
- `qwen3:14b` — mejor balance calidad/velocidad (default)
- `llama3.1:8b` — 2-3x más rápido, menos capaz
- `gemma3:12b` — mejor polaco/español si eso es prioridad
- `phi4:14b` — mejor seguimiento de XML en inglés, pero débil en multilingüe

---

## Cómo usarlo día a día

```cmd
REM Solo compilar — AUTO-GUARDA en ~/prompt-forge-outputs/*.xml
forge compile "ayudame a escribir un correo a mi jefe"

REM Guardar en distintos formatos (elige uno):
forge compile "..." --format md       REM Markdown (leíble en GitHub/editores)
forge compile "..." --format txt      REM texto plano
forge compile "..." --format xml      REM XML (default)
forge compile "..." --format html     REM HTML con estilos bonitos
forge compile "..." --format pdf      REM PDF (requiere reportlab)

REM Guardar en una ruta exacta
forge compile "..." -o C:\Users\Tu\Desktop\mi-prompt.md

REM Copiar al portapapeles automáticamente (listo para pegar)
forge compile "..." --copy

REM Combinado: guarda en markdown Y copia al clipboard
forge compile "..." --format md --copy

REM No guardar nada, solo mostrar en terminal
forge compile "..." --no-save

REM Compilar y ejecutar — TAMBIÉN guarda la respuesta del LLM
forge run "..." --format md --copy

REM Forzar un runner específico
forge run "..." --runner groq

REM Ver qué runners tienes configurados
forge runners

REM Crecer la base de conocimiento de técnicas
forge learn

REM Calificar el último output (mejora futuras compilaciones)
forge rate 5 --note "perfecto para mi caso"

REM Estadísticas
forge stats
```

### Dónde se guardan los archivos

Por defecto, todo se guarda en: **`C:\Users\TuUsuario\prompt-forge-outputs\`**

Los nombres se auto-generan con timestamp + slug del input, por ejemplo:
- `20260419-143022-prompt-ayudame-a-escribir-un-correo.xml`
- `20260419-143105-output-ayudame-a-escribir-un-correo.md`

Si usas `-o` con una ruta explícita, se guarda exactamente ahí.

### Formatos disponibles

| Formato | Cuándo usarlo |
|---------|---------------|
| **xml** (default) | Para pegar en otro LLM, o archivar el prompt crudo |
| **md** | Para editar/revisar en GitHub, Obsidian, VS Code |
| **txt** | Máxima compatibilidad, cualquier editor |
| **html** | Para abrir bonito en el navegador |
| **pdf** | Para imprimir o compartir formalmente (requiere `pip install reportlab`) |

> Si no instalas `reportlab`, `--format pdf` generará un HTML en su lugar — puedes usar **Ctrl+P → Guardar como PDF** en el navegador.

## Estrategia recomendada según el caso

| Situación | Runner recomendado |
|-----------|-------------------|
| Trabajo general, escritura, análisis | **Gemini 2.5 Pro** (tier 1) |
| Código iterativo que necesita ser rápido | **Groq** (tier 2) |
| Traducciones/resúmenes en batch | **Cerebras** (tier 3) |
| Datos sensibles de clientes | **Ollama local** (tier 4) |
| Sin internet | **Ollama local** (tier 4) |
| Prototipo rápido | Cualquiera, `forge run --runner auto` |

---

## Troubleshooting

**"No runners available"** → configuraste una variable pero la terminal no la ve. Cierra todas las ventanas de terminal y vuelve a abrirlas. PowerShell a veces requiere reiniciar.

**Ollama dice "model not found"** → la primera ejecución hace `ollama pull` automáticamente (~9GB). Espera. Si se interrumpe, ejecuta manualmente: `ollama pull qwen3:14b`.

**"HTTP 429: rate limit exceeded"** → usaste todo el tier gratuito. Espera al siguiente día, o configura otro tier como fallback.

**Ollama súper lento** → es normal en CPU. Si te molesta, usa los tiers cloud. Si insistes en local, prueba `FORGE_OLLAMA_MODEL=llama3.1:8b` (el doble de rápido, algo menos capaz).
