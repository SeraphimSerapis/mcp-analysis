"""Allow running with: python -m mcp_analysis"""

import sys

from mcp_analysis.cli import main

try:
    main()
except KeyboardInterrupt:
    sys.exit(130)
