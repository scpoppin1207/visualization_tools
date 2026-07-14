import mitsuba as mi


def init_mitsuba():
    """Initialize Mitsuba with CUDA, LLVM, or scalar fallback."""
    for variant in ("cuda_ad_rgb", "llvm_ad_rgb", "scalar_rgb"):
        try:
            mi.set_variant(variant)
            print(f"Using {variant.split('_')[0].upper()} variant")
            return variant
        except Exception:
            continue
    raise RuntimeError("Failed to initialize any Mitsuba variant")
