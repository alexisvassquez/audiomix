# AudioMIX
# runtime/dsl_helpers.py

from itertools import cycle as itercycle, islice
import types

# Functional tools for AudioScript (AS) v0.2

# Repeats a list or string forever (lazy generator)
def repeat(pattern):
    if isinstance(pattern, (list, str)):
        return itercycle(pattern)
    raise TypeError("repeat() expects a list or string")

# Takes the first n elements from any iterable
def take(n, iterable):
    return list(islice(iterable, n))

# Every nth execution
# Returns true only on those intervals (e.g., for LED strobe)
def every(n):
    count = 0
    while True:
        yield (count % n == 0)
        count += 1

# Compose multiple transformations (pure functions)
def compose(*funcs):
    def composed(x):
        for f in reversed(funcs):
            x = f(x)
        return x
    return composed

# Map a function over a pattern
# Currently list-based
def fmap(func, pattern):
    if isinstance(pattern, list):
        return list(map(func, pattern))
    raise TypeError("fmap expects a list")

# Apply transformation n times
def repeat_fn(f, times):
    def repeated(x):
        for _ in range(times):
            x = f(x)
        return x
    return repeated

# Function chaining syntax sugar
def chain(value, *funcs):
    for f in funcs:
        value = f(value)
    return value

# FX transformations
def stutter(n):
    def fx(pattern):
        return [beat for beat in pattern for _ in range(n)]
    return fx

def reverb(pattern):
    return pattern + ["-"]

# Registrable for 'with' chain
def get_fx_registry():
    return {
        "stutter": stutter,
        "reverb": reverb
    }

# Simulates 'play(...)' with fx
def apply_fx_chain(pattern, fx_chain):
    for fx in fx_chain:
        pattern = fx(pattern)
    return pattern
