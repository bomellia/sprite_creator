# 以下フォーマットのtxtを読み込み、その座標の画像を切り取るコード
# #long_active
# 0,1,306,2
# #long_normal
# 0,5,306,2
# #long_critical_active
# 0,9,306,2
# #long_critical_normal
# 0,13,306,2

# # notes_0.png
# 354,1100,354,186
# # notes_3.png
# 0,1286,354,186
# # notes_1.png
# 872,658,354,186
# # notes_2.png
# 708,1100,354,186

import os
import json
import cv2
import numpy as np

OUTPUT_DIR = 'output'

# 画像を切り取る helper
# 画像外の領域は透明(またはゼロ)でパディングして返す
def cut_image(image, x, y, width, height):
    h, w = image.shape[:2]
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(w, x + width)
    y1 = min(h, y + height)

    if x0 >= x1 or y0 >= y1:
        channels = 1 if image.ndim == 2 else image.shape[2]
        if channels == 1:
            return np.zeros((height, width), dtype=image.dtype)
        return np.zeros((height, width, channels), dtype=image.dtype)

    cropped = image[y0:y1, x0:x1]
    if x == x0 and y == y0 and cropped.shape[1] == width and cropped.shape[0] == height:
        return cropped

    channels = 1 if image.ndim == 2 else image.shape[2]
    if channels == 1:
        result = np.zeros((height, width), dtype=image.dtype)
    else:
        result = np.zeros((height, width, channels), dtype=image.dtype)

    dy = y0 - y
    dx = x0 - x
    result[dy:dy + cropped.shape[0], dx:dx + cropped.shape[1]] = cropped
    return result

# txt 形式の spr パターンを処理する
def process_txt_spr(image, coordinate_path):
    with open(coordinate_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    filename = None
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('#'):
            filename = line[1:].strip()
            filename = filename.replace(' ', '').replace('.png', '')
            continue

        if filename is None:
            print(f'警告: 出力ファイル名が設定されていません。コメント行を先に置いてください: {coordinate_path}')
            continue

        x, y, width, height = map(int, line.split(','))
        cropped = cut_image(image, x, y, width, height)
        cv2.imwrite(os.path.join(OUTPUT_DIR, f'{filename}.png'), cropped)

# json 形式の spr パターンを処理する
def process_json_spr(image, coordinate_path, base_name):
    with open(coordinate_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    sprites = data.get('sprites', [])
    if not isinstance(sprites, list):
        print(f'警告: sprites 配列が見つかりません: {coordinate_path}')
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # mmw_baseフォルダに出力する
    os.makedirs(os.path.join(OUTPUT_DIR, 'mmw_base'), exist_ok=True)

    for index, sprite in enumerate(sprites):
        if not all(k in sprite for k in ('x', 'y', 'w', 'h')):
            print(f'警告: sprite オブジェクトに x,y,w,h が含まれていません: {sprite}')
            continue

        x = int(sprite['x'])
        y = int(sprite['y'])
        width = int(sprite['w'])
        height = int(sprite['h'])
        cropped = cut_image(image, x, y, width, height)

        name = sprite.get('name') or f'{base_name}_{index}'
        name = str(name).replace(' ', '_').replace('.png', '')
        cv2.imwrite(os.path.join(OUTPUT_DIR, 'mmw_base', f'{name}.png'), cropped)


def resize_image_to_target(image, target_size, mode='linear'):
    width, height = target_size
    if mode == 'depth':
        src = np.float32([
            [0, 0],
            [image.shape[1] - 1, 0],
            [image.shape[1] - 1, image.shape[0] - 1],
            [0, image.shape[0] - 1],
        ])
        depth_shift = int(image.shape[0] * 0.12)
        dst = np.float32([
            [depth_shift, 0],
            [image.shape[1] - 1 - depth_shift, 0],
            [image.shape[1] - 1, image.shape[0] - 1],
            [0, image.shape[0] - 1],
        ])
        matrix = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(image, matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return cv2.resize(warped, (width, height), interpolation=cv2.INTER_LINEAR)

    interpolation = cv2.INTER_LINEAR
    return cv2.resize(image, (width, height), interpolation=interpolation)


def adjust_image_hsv(image, hue_shift=0, sat_scale=1.0, val_scale=1.0):
    if image is None or image.ndim < 3 or image.shape[2] < 3:
        return image

    alpha = None
    if image.shape[2] == 4:
        bgr = image[:, :, :3]
        alpha = image[:, :, 3]
    else:
        bgr = image

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_scale, 0, 255)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * val_scale, 0, 255)
    adjusted = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    if alpha is not None:
        adjusted = np.dstack((adjusted, alpha))
    return adjusted


def adjust_image_brightness_contrast(image, brightness=0, contrast=1.0):
    if image is None:
        return image

    alpha = None
    if image.ndim == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3]
        image = image[:, :, :3]

    result = image.astype(np.float32)
    result = result * float(contrast) + float(brightness)
    result = np.clip(result, 0, 255).astype(np.uint8)

    if alpha is not None:
        result = np.dstack((result, alpha))
    return result


def apply_color_adjustments(image, adjustments, brightness=0, contrast=1.0):
    if not adjustments and brightness == 0 and contrast == 1.0:
        return image
    hue_shift = adjustments.get('hue', 0) if isinstance(adjustments, dict) else 0
    sat_scale = adjustments.get('sat', 1.0) if isinstance(adjustments, dict) else 1.0
    val_scale = adjustments.get('val', 1.0) if isinstance(adjustments, dict) else 1.0
    image = adjust_image_hsv(image, hue_shift=hue_shift, sat_scale=sat_scale, val_scale=val_scale)
    if brightness != 0 or contrast != 1.0:
        image = adjust_image_brightness_contrast(image, brightness=brightness, contrast=contrast)
    return image


def load_particle_mmw(image, base_name):
    label_path = os.path.join('spr', f'{base_name}_labels.json')
    if not os.path.exists(label_path):
        print(f'対応するラベルファイルが見つかりません: {label_path}')
        return

    with open(label_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    if not isinstance(data, list):
        print(f'警告: レーベル JSON は配列である必要があります: {label_path}')
        return

    output_dir = os.path.join(OUTPUT_DIR, 'mmw')
    os.makedirs(output_dir, exist_ok=True)

    for index, sprite in enumerate(data):
        if not isinstance(sprite, dict) or not all(k in sprite for k in ('x', 'y', 'w', 'h')):
            print(f'警告: sprite オブジェクトに x,y,w,h が含まれていません: {sprite}')
            continue

        x = int(sprite['x'])
        y = int(sprite['y'])
        width = int(sprite['w'])
        height = int(sprite['h'])
        cropped = cut_image(image, x, y, width, height)

        label = sprite.get('label') or sprite.get('name') or f'{base_name}_{index}'
        label = str(label).strip() or f'{base_name}_{index}'
        label = label.replace(' ', '_').replace('.png', '')

        output_name = f'{label}.png'
        output_path = os.path.join(output_dir, output_name)
        # duplicate = 1
        # while os.path.exists(output_path):
        #     output_path = os.path.join(output_dir, f'{label}_{duplicate}.png')
        #     duplicate += 1

        cv2.imwrite(output_path, cropped)

# from_folder内のファイルと同名のファイルをtarget_folder内から探し、そのサイズに引き延ばす
# 引き延ばし手法として単純な線形引き延ばし・曲座標変換(奥行きを持つように引き延ばす)から選べるようにする
# さらに、一部ファイルに対しては色相や明度・彩度変更もできるようにする(配列で指定する)
def load_modify_config(config_path):
    if not os.path.exists(config_path):
        print(f'設定ファイルが見つかりません: {config_path}')
        return {}

    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
        except Exception as exc:
            print(f'設定ファイルの読み込みに失敗しました: {exc}')
            return {}

    if not isinstance(config, dict):
        print(f'設定ファイルはオブジェクト形式である必要があります: {config_path}')
        return {}

    return config


def resolve_modify_settings(filename, config):
    base_name = os.path.splitext(filename)[0]
    entry = {}

    file_entry = {}
    if isinstance(config.get('files'), dict):
        file_entry = config['files'].get(filename) or config['files'].get(base_name) or {}

    entry['mode'] = file_entry.get('mode') or config.get('default_mode', 'linear')
    entry['color_adjustments'] = file_entry.get('color_adjustments') or config.get('default_color_adjustments')
    entry['brightness'] = file_entry.get('brightness') if file_entry.get('brightness') is not None else config.get('default_brightness', 0)
    entry['contrast'] = file_entry.get('contrast') if file_entry.get('contrast') is not None else config.get('default_contrast', 1.0)
    return entry

import img_mod_alt as img_mod
def modify_particle_mmw(from_folder, target_folder, mode='linear', color_adjustments=None, config_path=None):
    """
    from_folder 内の PNG ファイルと同名の target_folder 内ファイルを探し、
    そのサイズに合わせて引き延ばします。

    mode:
      - 'linear' : 単純な線形補間リサイズ
      - 'depth'  : 奥行きを持つような変換を組み合わせたリサイズ

    color_adjustments:
      - None : 色調整なし
      - dict : {'hue': 10, 'sat': 1.2, 'val': 0.9}
      - list : [{'file': 'a.png', 'hue': 10, 'sat': 1.2, 'val': 0.9}]

    config_path:
      - JSON ファイルを指定すると、ファイル毎の mode と color_adjustments を読み込みます
    """
    if config_path:
        config = load_modify_config(config_path)
    else:
        config = {}

    if not os.path.isdir(from_folder):
        print(f'from_folder が存在しません: {from_folder}')
        return
    if not os.path.isdir(target_folder):
        print(f'target_folder が存在しません: {target_folder}')
        return

    output_dir = os.path.join(OUTPUT_DIR, 'modified')
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(from_folder):
        if not filename.lower().endswith('.png'):
            continue

        from_path = os.path.join(from_folder, filename)
        target_path = os.path.join(target_folder, filename)

        if not os.path.exists(target_path):
            print(f'対応するターゲットファイルが見つかりません: {target_path}')
            continue

        from_image = cv2.imread(from_path, cv2.IMREAD_UNCHANGED)
        target_image = cv2.imread(target_path, cv2.IMREAD_UNCHANGED)

        if from_image is None or target_image is None:
            print(f'画像の読み込みに失敗しました: {from_path} または {target_path}')
            continue

        settings = resolve_modify_settings(filename, config)
        file_mode = settings.get('mode') or mode
        file_adjustment = settings.get('color_adjustments') or color_adjustments
        brightness = settings.get('brightness', 0)
        contrast = settings.get('contrast', 1.0)

        modified_image = resize_image_to_target(
            from_image,
            (target_image.shape[1], target_image.shape[0]),
            mode=file_mode,
        )

        adjustment = None
        if isinstance(file_adjustment, dict):
            if all(k in file_adjustment for k in ('hue', 'sat', 'val')):
                adjustment = file_adjustment
            else:
                adjustment = file_adjustment.get(filename) or file_adjustment.get(os.path.splitext(filename)[0])
        elif isinstance(file_adjustment, list):
            for item in file_adjustment:
                if not isinstance(item, dict):
                    continue
                name = item.get('file') or item.get('name')
                if name and (name == filename or name == os.path.splitext(filename)[0]):
                    adjustment = item
                    break

        modified_image = apply_color_adjustments(modified_image, adjustment, brightness=brightness, contrast=contrast)

        # img_mod_alt によるアルファ正規化（最大が 1.0 になるように）
        try:
            modified_image = img_mod.normalize_alpha_max1(modified_image)
        except Exception:
            pass

        # modified フォルダに出力する
        output_path = os.path.join(output_dir, f'{filename}')
        cv2.imwrite(output_path, modified_image)

def merge_particle_to_sonolus(input_folder, sprite_json_path, output_path):
    # particle.jsonのsprites配列の順番通りに画像を張り付けていく
    # [
    #     {
    #         "x": 686,
    #         "y": 749,
    #         "w": 54,
    #         "h": 92// particle_0.png
    #     },
    #     {
    #         "x": 254,
    #         "y": 749,
    #         "w": 122,
    #         "h": 122// particle_1.png
    #     },...]
    if not os.path.exists(sprite_json_path):
        alternative = os.path.join('spr', 'particle.json')
        if os.path.exists(alternative):
            print(f'警告: {sprite_json_path} が見つかりません。代わりに {alternative} を使用します。')
            sprite_json_path = alternative
        else:
            print(f'sprite_json_path が見つかりません: {sprite_json_path}')
            return

    with open(sprite_json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    sprites = data.get('sprites', [])
    if not isinstance(sprites, list):
        print(f'警告: sprites 配列が見つかりません: {sprite_json_path}')
        return

    canvas_width = max(sprite['x'] + sprite['w'] for sprite in sprites)
    canvas_height = max(sprite['y'] + sprite['h'] for sprite in sprites)
    canvas = np.zeros((canvas_height, canvas_width, 4), dtype=np.uint8)

    for index, sprite in enumerate(sprites):
        name = sprite.get('name') or f'particle_{index}'
        name = str(name).strip() or f'particle_{index}'
        name = name.replace(' ', '_').replace('.png', '')
        image_path = os.path.join(input_folder, f'{name}.png')
        if not os.path.exists(image_path):
            print(f'対応する画像ファイルが見つかりません: {image_path}')
            continue

        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            print(f'画像の読み込みに失敗しました: {image_path}')
            continue

        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
        elif image.shape[2] == 3:
            alpha = np.full((image.shape[0], image.shape[1], 1), 255, dtype=np.uint8)
            image = np.dstack((image, alpha))
        elif image.shape[2] != 4:
            print(f'サポートされていないチャンネル数の画像です: {image_path}')
            continue

        x, y, w, h = int(sprite['x']), int(sprite['y']), int(sprite['w']), int(sprite['h'])
        if image.shape[1] != w or image.shape[0] != h:
            image = resize_image_to_target(image, (w, h), mode='linear')

        region = canvas[y:y+h, x:x+w]
        if region.shape != image.shape:
            print(f'配置領域と画像サイズが一致しません: {image_path} {region.shape} != {image.shape}')
            continue

        src = image.astype(np.float32) / 255.0
        dst = region.astype(np.float32) / 255.0
        src_rgb = src[:, :, :3]
        src_alpha = src[:, :, 3:4]
        dst_rgb = dst[:, :, :3]
        dst_alpha = dst[:, :, 3:4]

        out_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)
        safe_alpha = np.maximum(out_alpha, 1e-6)
        out_rgb = (src_rgb * src_alpha + dst_rgb * dst_alpha * (1.0 - src_alpha)) / safe_alpha
        zero_mask = (out_alpha[:, :, 0] <= 0)
        out_rgb[zero_mask] = 0.0

        blended = np.concatenate((out_rgb, out_alpha), axis=2)
        canvas[y:y+h, x:x+w] = np.clip(blended * 255.0, 0, 255).astype(np.uint8)

    cv2.imwrite(output_path, canvas)

# spr ファイルのパターンを判別して処理を分岐する
def process_spr_file(image_path, coordinate_path):
    image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        print(f'画像の読み込みに失敗しました: {image_path}')
        return

    ext = os.path.splitext(coordinate_path)[1].lower()
    base_name = os.path.splitext(os.path.basename(image_path))[0]

    if ext == '.txt':
        process_txt_spr(image, coordinate_path)
    elif ext == '.json':
        process_json_spr(image, coordinate_path, base_name)
    else:
        with open(coordinate_path, 'r', encoding='utf-8') as file:
            text = file.read().strip()
        if text.startswith('{'):
            process_json_spr(image, coordinate_path, base_name)
        else:
            process_txt_spr(image, coordinate_path)

# 1: カレントディレクトリの png 名称をすべて取得
# 2: 対応する txt または json が spr フォルダにあれば読み込む
# 3: process_spr_file を呼び出す
def main():
    png_files = [f for f in os.listdir('.') if f.endswith('.png')]

    for png_file in png_files:
        base_name = os.path.splitext(png_file)[0]
        txt_file = os.path.join('spr', f'{base_name}.txt')
        json_file = os.path.join('spr', f'{base_name}.json')

        if png_file == 'tex_note_common_all_v2.png':
            image = cv2.imread(png_file, cv2.IMREAD_UNCHANGED)
            if image is None:
                print(f'画像の読み込みに失敗しました: {png_file}')
                continue
            else:
                load_particle_mmw(image, base_name)
                modify_particle_mmw(os.path.join(OUTPUT_DIR, 'mmw'), os.path.join(OUTPUT_DIR, 'mmw_base'), mode='depth', config_path=os.path.join('spr', 'particle_modify_config.json'))
                merge_particle_to_sonolus(os.path.join(OUTPUT_DIR, 'modified'), os.path.join('spr', 'particle.json'), os.path.join(OUTPUT_DIR, 'sonolus_particle.png'))

        elif os.path.exists(txt_file):
            process_spr_file(png_file, txt_file)
        elif os.path.exists(json_file):
            process_spr_file(png_file, json_file)
        else:
            print(f'対応する spr ファイルが見つかりません: {txt_file} または {json_file}')

if __name__ == '__main__':
    main()
