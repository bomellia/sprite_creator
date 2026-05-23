def additive_to_normal_rgba(img):
    """
    加算発光向け画像を通常RGBA向けへ変換
    alphaフェード保持版
    """

    bgr, original_alpha = split_image_channels(img)

    intensity = calculate_light_intensity(bgr)

    alpha = extract_alpha(
        img,
        original_alpha,
        intensity
    )

    rgb = normalize_rgb_by_alpha(
        bgr,
        alpha
    )

    rgb = enhance_glow_color(rgb)

    rgb = apply_bloom_bakedown(
        rgb,
        alpha
    )

    # premultしない
    rgba = compose_rgba(
        rgb,
        alpha
    )

    return rgba


def split_image_channels(img):

    import numpy as np

    if img.shape[2] == 3:

        bgr = img.astype(np.float32) / 255.0

        alpha = np.max(
            bgr,
            axis=2
        )

    else:

        bgr = (
            img[..., :3]
            .astype(np.float32)
            / 255.0
        )

        alpha = (
            img[..., 3]
            .astype(np.float32)
            / 255.0
        )

    return bgr, alpha


def calculate_light_intensity(bgr):

    import numpy as np

    return np.max(
        bgr,
        axis=2
    )


def extract_alpha(
    img,
    original_alpha,
    intensity
):

    import numpy as np

    if img.shape[2] >= 4:

        alpha = original_alpha.copy()
        zero_mask = alpha <= 1e-5

        if np.any(zero_mask):
            generated = np.power(
                intensity,
                0.9
            )
            generated = np.clip(
                generated,
                0,
                1
            )
            # generated = apply_glow_spread(generated)
            alpha[zero_mask] = generated[zero_mask]

    else:

        alpha = np.power(
            intensity,
            0.9
        )
        alpha = np.clip(
            alpha,
            0,
            1
        )
        # alpha = apply_glow_spread(alpha)

    return alpha


def normalize_rgb_by_alpha(
    bgr,
    alpha
):

    import numpy as np

    rgb = np.zeros_like(bgr)

    mask = alpha > 1e-5

    rgb[mask] = (
        bgr[mask]
        / alpha[mask][:, None]
    )

    rgb = np.clip(
        rgb,
        0,
        1
    )

    return rgb


def enhance_glow_color(rgb):

    import cv2
    import numpy as np

    # ----------------------------------------
    # glow補正
    # ----------------------------------------

    rgb = np.power(
        rgb,
        0.92
    )

    hsv = cv2.cvtColor(
        (rgb * 255).astype(np.uint8),
        cv2.COLOR_BGR2HSV
    ).astype(np.float32)

    # 彩度強化
    hsv[..., 1] *= 1.08

    # 発光感
    hsv[..., 2] *= 1.04

    hsv[..., 1] = np.clip(
        hsv[..., 1],
        0,
        255
    )

    hsv[..., 2] = np.clip(
        hsv[..., 2],
        0,
        255
    )

    rgb = cv2.cvtColor(
        hsv.astype(np.uint8),
        cv2.COLOR_HSV2BGR
    ).astype(np.float32) / 255.0

    # 白寄りに寄せるために、微量のホワイトバイアスを加える
    white_bias = 0.08
    rgb = rgb * (1.0 - white_bias) + white_bias
    return np.clip(rgb, 0, 1)


def apply_bloom_bakedown(
    rgb,
    alpha
):

    import cv2
    import numpy as np

    # ----------------------------------------
    # 明部抽出
    # ----------------------------------------

    bright = np.maximum(
        rgb - 0.6,
        0
    )

    blur = cv2.GaussianBlur(
        bright,
        (0, 0),
        3.0
    )

    rgb = np.clip(
        rgb + blur * 0.4,
        0,
        1
    )

    # ----------------------------------------
    # alpha edge preservation
    # ----------------------------------------

    rgb *= (
        0.7 + alpha[..., None] * 0.3
    )

    return rgb


def compose_rgba(
    rgb,
    alpha
):

    import numpy as np

    out = np.dstack([
        rgb,
        alpha
    ])

    out = np.clip(
        out * 255,
        0,
        255
    ).astype(np.uint8)

    return out