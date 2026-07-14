import colorsys

import numpy as np


def enhance_colors_hsv(colors, brightness_factor=1.5, saturation_factor=1.5):
    """Enhance colors using HSV space transformation."""
    enhanced_colors = np.zeros_like(colors)

    for i in range(len(colors)):
        h, s, v = colorsys.rgb_to_hsv(colors[i, 0], colors[i, 1], colors[i, 2])
        s = min(1.0, s * saturation_factor)
        v = min(1.0, v * brightness_factor)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        enhanced_colors[i] = [r, g, b]

    return enhanced_colors


def enhance_colors_gamma(colors, gamma=0.7):
    """Enhance colors using gamma correction."""
    return np.power(colors, gamma)


def enhance_colors_log(colors, scale=1.2):
    """Enhance colors using logarithmic transformation."""
    colors_safe = np.clip(colors, 1e-8, 1.0)
    enhanced = np.log(1 + colors_safe * scale) / np.log(1 + scale)
    return np.clip(enhanced, 0, 1)


def enhance_colors_adaptive(colors, target_brightness=0.6):
    """Adaptively enhance colors based on original brightness."""
    brightness = 0.299 * colors[:, 0] + 0.587 * colors[:, 1] + 0.114 * colors[:, 2]
    enhancement_factor = np.where(
        brightness > 0,
        np.minimum(target_brightness / brightness, 3.0),
        1.0,
    )
    enhanced_colors = colors * enhancement_factor[:, np.newaxis]
    return np.clip(enhanced_colors, 0, 1)
