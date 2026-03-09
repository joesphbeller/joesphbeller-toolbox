#!/usr/bin/env python3
# Thanks to this article for the idea: https://blog.simonfarshid.com/adapting-illustrations-to-dark-mode
# Thanks to Github Copilot for helping me quickly implement the code. Specificially, handling the file reading, output, and details regarding which image processing package to use.
"""
Image Color Inversion and Hue Rotation Script

This script reads an image, inverts its colors, applies a 180-degree hue rotation,
and saves the result with '_inverted' appended to the filename.
"""

import sys
import os
from pathlib import Path
from PIL import Image
import numpy as np


def rgb_to_hsv(rgb):
    """Convert RGB image array to HSV."""
    rgb = rgb.astype(np.float32) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    v = maxc
    
    deltac = maxc - minc
    s = np.where(maxc != 0, deltac / maxc, 0)
    
    rc = np.where(deltac != 0, (maxc - r) / deltac, 0)
    gc = np.where(deltac != 0, (maxc - g) / deltac, 0)
    bc = np.where(deltac != 0, (maxc - b) / deltac, 0)
    
    h = np.zeros_like(r)
    h = np.where(r == maxc, bc - gc, h)
    h = np.where(g == maxc, 2.0 + rc - bc, h)
    h = np.where(b == maxc, 4.0 + gc - rc, h)
    h = np.where(deltac == 0, 0, h)
    
    h = (h / 6.0) % 1.0
    
    return np.stack([h, s, v], axis=2)


def hsv_to_rgb(hsv):
    """Convert HSV image array to RGB."""
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    
    i = (h * 6.0).astype(np.int32)
    f = (h * 6.0) - i
    
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    i = i % 6
    
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    
    rgb = np.stack([r, g, b], axis=2)
    rgb = (rgb * 255).astype(np.uint8)
    
    return rgb


def invert_colors(image):
    """Invert the colors of an RGB image."""
    img_array = np.array(image)
    inverted = 255 - img_array
    return Image.fromarray(inverted.astype(np.uint8))


def rotate_hue(image, degrees):
    """Rotate the hue of an image by specified degrees."""
    img_array = np.array(image)
    
    # Convert to HSV
    hsv = rgb_to_hsv(img_array)
    
    # Rotate hue (degrees / 360)
    hue_shift = (degrees % 360) / 360.0
    hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 1.0
    
    # Convert back to RGB
    rgb = hsv_to_rgb(hsv)
    
    return Image.fromarray(rgb)


def process_image(input_path):
    """
    Process an image: invert colors and rotate hue by 180 degrees.
    
    Args:
        input_path: Path to the input image file
        
    Returns:
        Path to the output image file
    """
    # Load the image
    try:
        img = Image.open(input_path)
        # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
        if img.mode != 'RGB':
            img = img.convert('RGB')
    except Exception as e:
        print(f"Error loading image: {e}")
        return None
    
    print(f"Processing image: {input_path}")
    print(f"Original size: {img.size}, mode: {img.mode}")
    
    # Step 1: Invert colors
    img_inverted = invert_colors(img)
    
    # Step 2: Rotate hue by 180 degrees
    img_final = rotate_hue(img_inverted, 180)
    
    # Generate output filename
    path = Path(input_path)
    output_filename = f"{path.stem}_inverted{path.suffix}"
    output_path = path.parent / output_filename
    
    # Save the processed image
    try:
        img_final.save(output_path)
        print(f"Saved processed image to: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error saving image: {e}")
        return None


def main():
    """Main function to handle command-line arguments."""
    if len(sys.argv) < 2:
        print("Usage: python invert_figure.py <image_path>")
        print("Example: python invert_figure.py my_image.png")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' does not exist.")
        sys.exit(1)
    
    result = process_image(input_path)
    
    if result:
        print("Processing complete!")
    else:
        print("Processing failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
