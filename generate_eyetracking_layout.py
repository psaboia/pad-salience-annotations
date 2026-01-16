#!/usr/bin/env python3
"""
Generate an image showing the eye-tracking layout with AprilTags and PAD image.
This image can be given to participants to show what the eye-tracking surface looks like.
"""

import argparse
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont


def generate_eyetracking_layout(
    pad_image_path: Optional[str] = None,
    output_path: str = "eyetracking_layout.png",
    tag_size: int = 80,
    tag_margin: int = 20,
    background_color: str = "#1a1a2e",
):
    """
    Generate an image showing the eye-tracking layout.

    Args:
        pad_image_path: Path to a PAD image to use. If None, uses first available sample.
        output_path: Where to save the generated image.
        tag_size: Size of AprilTag markers in pixels.
        tag_margin: Margin between tags and the PAD image.
        background_color: Background color (hex).
    """
    base_dir = Path(__file__).parent

    # Load AprilTags
    tags_dir = base_dir / "assets" / "apriltags"
    tag_files = {
        "top_left": tags_dir / "tag36h11_0.png",
        "top_right": tags_dir / "tag36h11_3.png",
        "bottom_left": tags_dir / "tag36h11_7.png",
        "bottom_right": tags_dir / "tag36h11_4.png",
    }

    tags = {}
    for position, path in tag_files.items():
        if path.exists():
            tag = Image.open(path).convert("RGBA")
            tag = tag.resize((tag_size, tag_size), Image.NEAREST)
            tags[position] = tag
        else:
            print(f"Warning: AprilTag not found at {path}")
            return None

    # Load PAD image
    if pad_image_path:
        pad_path = Path(pad_image_path)
    else:
        # Use first available sample
        samples_dir = base_dir / "sample_images"
        sample_files = list(samples_dir.glob("*.png"))
        if not sample_files:
            print("Error: No sample images found")
            return None
        pad_path = sample_files[0]

    if not pad_path.exists():
        print(f"Error: PAD image not found at {pad_path}")
        return None

    pad_image = Image.open(pad_path).convert("RGBA")
    pad_width, pad_height = pad_image.size

    # Calculate canvas size
    # Layout: [tag] [margin] [PAD image] [margin] [tag]
    canvas_width = tag_size + tag_margin + pad_width + tag_margin + tag_size
    canvas_height = tag_size + tag_margin + pad_height + tag_margin + tag_size

    # Create canvas
    bg_color = tuple(int(background_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    canvas = Image.new("RGB", (canvas_width, canvas_height), bg_color)

    # Calculate positions
    pad_x = tag_size + tag_margin
    pad_y = tag_size + tag_margin

    # Paste PAD image
    canvas.paste(pad_image, (pad_x, pad_y))

    # Add white background behind tags for visibility
    tag_positions = {
        "top_left": (0, 0),
        "top_right": (canvas_width - tag_size, 0),
        "bottom_left": (0, canvas_height - tag_size),
        "bottom_right": (canvas_width - tag_size, canvas_height - tag_size),
    }

    # Paste tags with white background
    for position, (x, y) in tag_positions.items():
        # White background
        white_bg = Image.new("RGB", (tag_size, tag_size), (255, 255, 255))
        canvas.paste(white_bg, (x, y))
        # Tag image
        canvas.paste(tags[position], (x, y), tags[position])

    # Add tag labels
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except OSError:
        font = ImageFont.load_default()

    tag_labels = {
        "top_left": ("tag 0", (tag_size // 2, tag_size + 5)),
        "top_right": ("tag 3", (canvas_width - tag_size // 2, tag_size + 5)),
        "bottom_left": ("tag 7", (tag_size // 2, canvas_height - tag_size - 15)),
        "bottom_right": ("tag 4", (canvas_width - tag_size // 2, canvas_height - tag_size - 15)),
    }

    for label, (x, y) in tag_labels.values():
        try:
            text_width, _ = draw.textsize(label, font=font)
        except AttributeError:
            # Fallback for newer PIL versions
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
        draw.text((x - text_width // 2, y), label, fill="#666666", font=font)

    # Save
    output = Path(output_path)
    canvas.save(output, "PNG")
    print(f"Generated eye-tracking layout image: {output}")
    print(f"  Canvas size: {canvas_width} x {canvas_height}")
    print(f"  PAD image: {pad_path.name} ({pad_width} x {pad_height})")
    print(f"  Tag size: {tag_size}px")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Generate eye-tracking layout image with AprilTags"
    )
    parser.add_argument(
        "--pad-image",
        type=str,
        default=None,
        help="Path to PAD image (default: first available sample)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="eyetracking_layout.png",
        help="Output file path (default: eyetracking_layout.png)"
    )
    parser.add_argument(
        "--tag-size",
        type=int,
        default=80,
        help="AprilTag size in pixels (default: 80)"
    )
    parser.add_argument(
        "--tag-margin",
        type=int,
        default=20,
        help="Margin between tags and PAD image (default: 20)"
    )
    parser.add_argument(
        "--background",
        type=str,
        default="#1a1a2e",
        help="Background color in hex (default: #1a1a2e)"
    )

    args = parser.parse_args()

    generate_eyetracking_layout(
        pad_image_path=args.pad_image,
        output_path=args.output,
        tag_size=args.tag_size,
        tag_margin=args.tag_margin,
        background_color=args.background,
    )


if __name__ == "__main__":
    main()
