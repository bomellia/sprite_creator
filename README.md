# Sprite Creator Usage

## 必須ファイル

- `particle.png`
  - 変換先のリファレンス画像です。切り出した画像の変換先サイズの参照元として使われます。
- `tex_note_common_all_v2.png`
  - 変換元のソース画像です。ここに自作パーティクルを上書きしてください。
- `spr/particle_modify_config.json`
  - 発光加工や色調整、明るさ・コントラストを指定する設定ファイルです。
- `spr/particle.json`
  - Sonolus 用に出力する配置情報の参照ファイルです。
- `spr/tex_note_common_all_v2_labels.json`
  - `label_tool.py` で作成した mmw の座標と Sonolus データの対応付けを格納したラベルファイルです。

## 必要な Python パッケージ

```bash
pip install numpy opencv-python pillow
```

## 実行手順

1. リポジトリルートに移動します。

2. `tex_note_common_all_v2.png`を自作のものに差し替えます。

2. 変換を実行します。

```bash
python main.py
```

3. 出力結果は以下に生成されます。

- `output/mmw/`
  - `tex_note_common_all_v2.png` から切り出した mmw 画像
- `output/mmw_base/`
  - `spr/particle.json` の参照サイズに合わせた元画像からのリサイズ結果
- `output/modified/`
  - 色調整・発光加工が適用された画像
- `output/sonolus_particle.png`
  - Sonolus 用にマージした最終出力画像

4. 以下を実行することでこのパーティクルを含むscpファイルを生成できます。`config.json`を書き換えてから使用してください。

```bash
python scp_replace_texture_new.py
```

## ラベル編集と追加出力

`label_tool.py` を使って `spr/tex_note_common_all_v2_labels.json` の内容を確認・編集できます。

```bash
python label_tool.py
```

