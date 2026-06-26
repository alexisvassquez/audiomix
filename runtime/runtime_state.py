# audiomix
# AudioMIX
# runtime/runtime_state.py

# Central store for AS runtime variables and macros
from collections import defaultdict

# Stores all variables declared via 'let'
variables = {}

# Stores all user-defined macros declared via 'def'
macros = {}

# Stores reactive hooks like 'on mood("happy") { ... }
# e.g., event_hooks["mood:happy"] = [fn1, fn2]
event_hooks = defaultdict(list)

# Variable handling
def set_var(name, value):
    variables[name] = value

def get_var(name):
    return variables.get(name)

def has_var(name):
    return name in variables

# Macro handling
def register_macro(name, func):
    macros[name] = func

def get_macro(name):
    return macros.get(name)

def has_macro(name):
    return name in macros

# Event hooks
def register_event_hook(event_key, func):
    event_hooks[event_key].append(func)

def get_hooks(event_key):
    return event_hooks.get(event_key, [])

def trigger_event(event_key):
    for hook in get_hooks(event_key):
        try:
            hook()
        except Exception as e:
            print (f"[hook error] {e}")

# Debug tools
def dump_state():
    print ("\n[🌐 Runtime State Dump]")
    print ("Variables:", variables)
    print ("Macros:", list(macros.keys()))
    print ("Event Hooks:", dict(event_hooks))
