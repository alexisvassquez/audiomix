# AudioMIX
# version.py
from pathlib import Path
from datetime import datetime

# Redefine version metadata after code execution environment reset
version= "v0.3.0"
date = datetime.now().strftime("%Y-%m-%d")

# Generate version.py
version_file = f'''
"""
AudioMIX Version Metadata
"""

__version__ = "{version}"
_release_date__ = "{date}"
'''

# Save to root
version_path = Path("/home/wholesomedegenerate/audiomix/version.py")
version_path.write_text(version_file.strip())
