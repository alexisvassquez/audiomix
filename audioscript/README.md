# AudioScript (AS) Language Specification & Syntax Support

Welcome to the `audioscript/` directory - the official home of the **AudioScript (AS)** domain-specific language used in [AudioMIX](https://github.com/alexisvassquez/audiomix). **AudioScript** is a modular, *expressive*, and now **functional-reactive** scripting language designed to power **real-time music behavior, emotional audio cues, light-reactive visuals, and live performance logic** directly from the AS terminal.

> 🎛️  AudioScript is for those who feel sound, code emotion, and live at the intersection of creativity and computation.

---

## Included Files

| File | Purpose |
| ------ | --------- |
| `AudioScriptLive.ebnf` | Official EBNF grammar definition for AudioScript Live. Located in `live/` |
| `AudioScriptIR.ebnf` | Official EBNF grammar definition for AudioScript IR. Located in `ir`/ |
| `AUDIOSCRIPT_SPEC.md` | Markdown-based syntax + grammar reference |
| `audioscript.nanorc` | Syntax highlighting rules for GNU Nano (still being perfected) |
| `live/` | Directory for AudioScript Live with supported documents and examples |
| `intro_showcase.audioscript` | Showcase of new v0.2 features including `let`, `repeat`, `with` chaining. Located in `live/` directory. |
| `ir/` | Directory for AudioScript IR with supported documents and examples |
| `cvltiv8r_clean.as` | Example of a compiler-generated AudioScript IR file analyzed from a demo track. Located in `ir/` directory. |
| `scripts/` | Various example scripts |
| *Future* `audioscript.tmLanguage.json` | VS Code/TextMate syntax highlighting (in development) |
| *Future* `audioscript.vim` | Vim highlighting (in development) |

---

## Syntax Highlighting Setup (Nano)

To enable syntax highlighting for **AudioScript (AS)** in Nano:

1. Copy `audioscript.nanorc` into your Nano config directory:

```bash
mkdir -p ~/.nano
cp audioscript.nanorc ~/.nano.
```

2.Add the following line to you `~/.nanorc`:

```bash
include ~/.nano/audioscript.nanorc
```

3.Open your `.as` or `.audioscript` files like this:

```bash
nano -Y audioscript example.as
```

---

## About the Language

**AudioScript** syntax blends the *minimalism of Bash*, the *readability of Python*, and now the *lazy functional power of Haskell*. It is engineered for low-latency music programming, enabling instant response in performance - whether you're syncing audio, controlling LED arrays, or programming mood-reactive stage effects.

Core design influences:

- **Python** - for intuitive scripting and flow control
- **Haskell** - lazy evaluation, functional purity, infinite pattern generation
- **Shell/Bash** - for command-style expressiveness and minimalism
- **C / C++** - for speed, performance modules, PortAudio control
- **CMake** - for declarative, configuration-style logic

### 💡 New v0.2 Capabilities

- `let` expressions for variable storage (`let beat = repeat(["kick", "snare"])`)
- Lazy generators with `repeat()` and `take()`
- Function chaining with `with` (`play("track") with reverb + stutter(2)`)
- Pure function utilities (from `runtime/dsl_helpers.py`)
- Runtime context and event hook management
- CLI-based `.audioscript` and `.as` execution and interactive shell

### Core Commands

- `play()`, `pause()`, `stop()`, `rewind()` - Real-time audio control
- `glow()`, `pulse()`, `fade()` - Light + LED behavior
- `mood.set()` - Emotionally-reactive state transitions
- `let`, `def`, `on mood(...)` - Functional and reactive control flow

Declared file extensions:

- `.audioscript`
- `.as`

---

## AudioScript: Live vs IR

AudioScript is intentionally split into two layers:

- **AudioScript Live**
  - Human-authored
  - Used for live coding, performance logic, and creative control
  - Expressive, readable, and reactive

- **AudioScript IR (Intermediate Representation)**
  - Machine-generated
  - Engine-executable and deterministic
  - Used for playback, scheduling, and automation

AudioScript Live code is compiled or lowered into AudioScript IR before execution.
The AudioMIX engine primarily consumes IR, not Live syntax.

---

## 💚🎧 Made With Love

**AudioScript** is being actively developed as part of the **AudioMIX** project by *Alexis M Vasquez (@alexisvassquez)*, a terminal-loving creative engineer and musical systems thinker. If you'd like to contribute to syntax themes, runtime modules, parsers for your favorite editor, or share feedback, please feel free to open a PR, issue, or email [alexis@alexismvasquez.com](mailto:alexis@alexismvasquez.com).

---

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**.

This means:

- You are free to use, modify, and distribute the software.
- Any derivative work must also be open source under the same license.
- Commercial use is permitted as long as credit and license compliance are maintained.

[Read the full license →](https://www.gnu.org/licenses/gpl-3.0.en.html)
