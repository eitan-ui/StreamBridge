"""License code generator for StreamBridge.

Usage:
    python generate_license.py USERNAME

Where USERNAME is the name of the user to license.
"""

import sys
sys.path.insert(0, ".")

from utils.license import generate_activation_code

if len(sys.argv) < 2:
    print("Usage: python generate_license.py USERNAME")
    print("Example: python generate_license.py 'John Smith'")
    sys.exit(1)

username = " ".join(sys.argv[1:])
code = generate_activation_code(username)
print(f"\nUsername:         {username}")
print(f"Activation Code:  {code}")
print(f"\nGive this code to the user.")
