# AudioMIX
# performance_engine/utils/shell_output.py

def say(msg, icon=""):
    if isinstance(msg, str):
        for line in msg.strip().split("\n"):
            print (f"{icon} {line}".strip())
    elif isinstance(msg, list):
        for line in msg:
            print (f"{icon} {line}".strip())
    else:
        print (f"{icon} {str(msg)}".strip())
