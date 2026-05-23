"""
軽量な代替のイメージ補正ユーティリティ
- アルファを正規化して最大値が 1.0 になるようにする
- 元画像のアルファが存在する場合は相対フェードを維持（ただし全体をスケール）
- BGR / BGRA 入力を受け取り、BGRA (uint8) を返す
"""

import numpy as np


def normalize_alpha_max1(img):
    """入力画像（BGR または BGRA uint8）を受け取り、アルファチャネルを正規化して
    最大が 1.0（255）になるようにした BGRA uint8 を返します。

    元のアルファが存在する場合はその相対比を保ちつつ全体をスケーリングします。
    アルファが存在しない場合は RGB の最大値をアルファとして使用します。
    """
    if img is None:
        return img

    arr = img.copy()
    if arr.ndim < 3 or arr.shape[2] < 3:
        return img

    # RGB 部分を float [0,1]
    bgr = arr[..., :3].astype(np.float32) / 255.0

    # alpha を取得（存在すればそれを、なければ輝度由来で作る）
    if arr.shape[2] >= 4:
        alpha = arr[..., 3].astype(np.float32) / 255.0
        # 保守: もし RGB が既に premultiplied されている場合に備え、非 premultiplied 用の復元は行わない
    else:
        alpha = np.max(bgr, axis=2)

    maxa = float(np.max(alpha))
    if maxa > 1e-6:
        alpha = alpha / maxa
    else:
        # すべてゼロならそのまま返す（透明画像）
        alpha = alpha

    # 出力は BGRA uint8（RGB は元の色を保持）
    out_bgr = np.clip(bgr * 255.0, 0, 255).astype(np.uint8)
    out_a = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    out = np.dstack([out_bgr, out_a])
    return out


if __name__ == '__main__':
    # 簡易テスト（手元での利用向け）
    import cv2
    img = cv2.imread('test.png', cv2.IMREAD_UNCHANGED)
    if img is None:
        print('test.png が見つかりません')
    else:
        out = normalize_alpha_max1(img)
        cv2.imwrite('test_normalized.png', out)
