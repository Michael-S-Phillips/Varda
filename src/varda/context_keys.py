"""app_model context keys that drive menu/action enablement.

Kept free of other varda imports so both the actions and the GUI that updates
the keys can import it without cycles.
"""

from app_model.expressions import parse_expression

IMAGE_COUNT = "image_count"
WORKSPACE_COUNT = "workspace_count"

EXPR_HAS_IMAGES = parse_expression(f"{IMAGE_COUNT} > 0")
EXPR_HAS_WORKSPACE = parse_expression(f"{WORKSPACE_COUNT} > 0")
# For actions that should be listed but never enabled (missing optional dependency)
EXPR_NEVER = parse_expression("False")
