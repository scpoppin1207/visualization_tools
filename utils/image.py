import numpy as np
from PIL import Image


def remove_white_background(image_path):
    """Convert near-white pixels to transparent and save as *_t.png."""
    img = Image.open(image_path).convert("RGBA")
    data = np.array(img)

    white_areas = (data[:, :, 0] > 240) & (data[:, :, 1] > 240) & (data[:, :, 2] > 240)
    data[white_areas] = [255, 255, 255, 0]

    new_img = Image.fromarray(data, "RGBA")
    new_img.save(image_path.replace(".png", "_t.png"))


def center_crop_by_ratio(image_path, ratio=0.9):
    """Center-crop image by ratio and overwrite the original file."""
    assert 0 < ratio <= 1, "Ratio must be between 0 and 1."

    image = Image.open(image_path)
    width, height = image.size

    new_width = int(width * ratio)
    new_height = int(height * ratio)

    left = (width - new_width) // 2
    upper = (height - new_height) // 2
    right = left + new_width
    lower = upper + new_height

    cropped_image = image.crop((left, upper, right, lower))
    cropped_image.save(image_path)
    print(f"Cropped image saved. New size: {new_width} x {new_height}")
