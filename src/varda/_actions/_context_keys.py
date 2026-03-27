from app_model.expressions import parse_expression

IMAGE_COUNT = "image_count"
EXPR_HAS_IMAGES = parse_expression("image_count > 0")
