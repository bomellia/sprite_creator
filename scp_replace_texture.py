import argparse
import copy
import json
import os
import shutil
import tempfile
import uuid
import zipfile


def safe_extract(zip_file: zipfile.ZipFile, path: str) -> None:
    for member in zip_file.infolist():
        member_path = os.path.normpath(os.path.join(path, member.filename))
        if not member_path.startswith(os.path.abspath(path) + os.sep) and os.path.abspath(path) != member_path:
            raise RuntimeError(f'危険なパスを含むエントリを検出しました: {member.filename}')
        zip_file.extract(member, path)


def find_texture_url(info_path: str) -> str:
    with open(info_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f'info JSON のルートはオブジェクトである必要があります: {info_path}')

    sections = data.get('sections')
    if not isinstance(sections, list) or len(sections) == 0:
        raise ValueError(f'sections が見つかりません: {info_path}')

    items = sections[0].get('items')
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError(f'items が見つかりません: {info_path}')

    texture = items[0].get('texture')
    if not isinstance(texture, dict):
        raise ValueError(f'texture オブジェクトが見つかりません: {info_path}')

    url = texture.get('url')
    if not isinstance(url, str) or not url:
        raise ValueError(f'texture.url が見つかりません: {info_path}')

    return url


def find_info_file(extracted_root: str) -> str:
    candidates = []
    for dirpath, _, filenames in os.walk(extracted_root):
        for filename in filenames:
            if filename == 'info':
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, extracted_root).replace('\\', '/')
                if 'sonolus' in rel_path and 'particles' in rel_path:
                    return full_path
                candidates.append(full_path)
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f'info ファイルが見つかりません: {extracted_root}')


def replace_texture_file(extracted_root: str, texture_url: str, replacement_image_path: str) -> str:
    texture_path = texture_url.lstrip('/')
    destination_path = None
    candidates = [
        os.path.join(extracted_root, texture_path),
        os.path.join(extracted_root, 'scp', texture_path),
        os.path.join(extracted_root, 'scp', texture_path.lstrip('/')),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            destination_path = candidate
            break

    if destination_path is None:
        for dirpath, _, filenames in os.walk(extracted_root):
            for filename in filenames:
                rel = os.path.relpath(os.path.join(dirpath, filename), extracted_root).replace('\\', '/')
                if rel.endswith(texture_path):
                    destination_path = os.path.join(dirpath, filename)
                    break
            if destination_path is not None:
                break

    if destination_path is None:
        raise FileNotFoundError(f'置き換え対象のテクスチャが見つかりません: {texture_path}')

    if not os.path.isfile(replacement_image_path):
        raise FileNotFoundError(f'置き換え元画像が見つかりません: {replacement_image_path}')

    shutil.copy2(replacement_image_path, destination_path)
    return destination_path


def generate_new_texture_path(extracted_root: str, texture_url: str) -> str:
    # 新しいファイル名はランダムハッシュを利用する
    texture_path = texture_url.lstrip('/')
    texture_dir = os.path.dirname(texture_path)
    if not texture_dir:
        texture_dir = 'sonolus/repository'
    hash_name = uuid.uuid4().hex
    new_rel = os.path.join(texture_dir, hash_name).replace('\\', '/')
    return new_rel


def add_texture_file(extracted_root: str, texture_url: str, replacement_image_path: str) -> str:
    if not os.path.isfile(replacement_image_path):
        raise FileNotFoundError(f'追加元画像が見つかりません: {replacement_image_path}')

    new_rel = generate_new_texture_path(extracted_root, texture_url)
    destination_path = os.path.join(extracted_root, new_rel)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    shutil.copy2(replacement_image_path, destination_path)
    return '/' + new_rel.replace('\\', '/')


def update_info_texture(info_path: str, new_url: str) -> None:
    with open(info_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    sections = data.get('sections')
    items = sections[0].get('items')
    texture = items[0].get('texture')
    if not isinstance(texture, dict):
        raise ValueError(f'texture オブジェクトが見つかりません: {info_path}')

    texture['url'] = new_url
    if 'hash' in texture:
        texture['hash'] = os.path.basename(new_url)

    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def add_new_item_to_info(info_path: str, new_url: str, new_name: str = None) -> dict:
    """テンプレートアイテムを複製して `items` に新規追加し、追加したオブジェクトを返す。

    - `new_url` は `/sonolus/repository/...` 形式の相対パス文字列
    - `new_name` が指定されなければテンプレート名に `-copy` を付けて一意化する
    """
    with open(info_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError('info JSON の形式が不正です')

    sections = data.get('sections')
    if not isinstance(sections, list) or len(sections) == 0:
        raise ValueError('sections が見つかりません')

    items = sections[0].get('items')
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError('items が見つかりません')

    template = items[0]
    new_item = copy.deepcopy(template)

    # 名前を決定
    base_name = new_item.get('name', 'particle')
    if new_name:
        candidate = new_name
    else:
        candidate = f"{base_name}-copy"
    existing_names = {it.get('name') for it in items}
    if candidate in existing_names:
        candidate = f"{candidate}-{uuid.uuid4().hex[:8]}"

    new_item['name'] = candidate

    # テクスチャ情報を新しい URL/hash に差し替え
    if 'texture' not in new_item or not isinstance(new_item['texture'], dict):
        new_item['texture'] = {}
    new_item['texture']['url'] = new_url
    new_item['texture']['hash'] = os.path.basename(new_url)

    # 保守: data/thumbnail はテンプレートからそのまま引き継ぐ
    items.append(new_item)

    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    return new_item


def update_list_file(info_path: str, new_item: dict, new_texture_url: str) -> None:
    """list ファイル（UI用リスト）を更新してテンプレートをコピーし、新規アイテムを追加する。

    - テンプレート（最初のアイテム）を深くコピーして新規アイテムの情報で上書き
    - items 配列に追加し、list ファイルに保存
    """
    info_dir = os.path.dirname(info_path)
    list_path = os.path.join(info_dir, 'list')

    if not os.path.exists(list_path):
        print(f'list ファイルが見つかりません、スキップします: {list_path}')
        return

    try:
        with open(list_path, 'r', encoding='utf-8') as f:
            list_data = json.load(f)

        if not isinstance(list_data, dict):
            raise ValueError('list JSON の形式が不正です')

        items = list_data.get('items')
        if not isinstance(items, list) or len(items) == 0:
            print('list に items が見つかりません、スキップします')
            return

        # テンプレート（最初のアイテム）を深くコピー
        template_item = items[0]
        new_list_item = copy.deepcopy(template_item)

        # 新規アイテムの情報で上書き
        new_list_item['name'] = new_item.get('name')
        if 'texture' in new_item:
            new_list_item['texture'] = copy.deepcopy(new_item['texture'])
        # title や author などはテンプレートから引き継ぐ（必要に応じてカスタマイズ可能）

        # items 配列に追加
        items.append(new_list_item)

        # ファイルに保存
        with open(list_path, 'w', encoding='utf-8') as f:
            json.dump(list_data, f, ensure_ascii=False, indent=2)
            f.write('\n')

        print(f'list ファイルを更新しました: {list_path}')
    except Exception as exc:
        print(f'list ファイルの更新に失敗しました: {exc}')


def create_item_file_from_template(info_path: str, template_name: str, new_name: str, replacement_image_path: str, new_texture_url: str = None) -> str:
    """info と同じディレクトリにあるテンプレートファイルを複製し、新しい name のファイルを作る。

    Parameters:
    - new_texture_url: テクスチャの新しい URL。例: /sonolus/repository/73daf3319af4ebcbb1e6e8473c0a372
                      指定されない場合は new_name を使用
    - テンプレートが存在して JSON なら `item.name` と `item.texture.hash/url` を置き換える。
    - テンプレートがテキスト（JSON以外）なら、テキスト内の古いハッシュを置き換える。
    - テンプレートが存在しなければ `replacement_image_path` をコピーして代替ファイルを作る。
    返値: 作成したファイルの絶対パス
    """
    info_dir = os.path.dirname(info_path)
    template_path = os.path.join(info_dir, template_name)
    new_path = os.path.join(info_dir, new_name)

    if os.path.exists(template_path):
        try:
            with open(template_path, 'rb') as f:
                raw = f.read()

            # JSON として解析を試みる
            text = None
            try:
                text = raw.decode('utf-8')
                data = json.loads(text)
                # JSON 形式なら item.name と item.texture を置き換える
                if isinstance(data, dict) and 'item' in data:
                    item = data['item']
                    if isinstance(item, dict):
                        item['name'] = new_name
                        # texture ハッシュ値を設定
                        if 'texture' not in item:
                            item['texture'] = {}
                        if not isinstance(item['texture'], dict):
                            item['texture'] = {}
                        
                        # new_texture_url が指定されている場合は、それを使用
                        if new_texture_url:
                            item['texture']['hash'] = os.path.basename(new_texture_url)
                            item['texture']['url'] = new_texture_url
                        else:
                            # デフォルトは new_name を使用
                            item['texture']['hash'] = new_name
                            item['texture']['url'] = f'/sonolus/repository/{new_name}'
                        
                        # JSON を整形して保存
                        with open(new_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=4)
                        return new_path
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

            # JSON 失敗時、プレーンテキストとして処理
            if text is not None:
                # テンプレートの info から古い texture.hash を探して置換する
                try:
                    with open(info_path, 'r', encoding='utf-8') as f:
                        info_data = json.load(f)
                    old_hash = info_data['sections'][0]['items'][0].get('texture', {}).get('hash')
                except Exception:
                    old_hash = None

                new_text = text
                if old_hash:
                    new_text = new_text.replace(old_hash, new_name)

                with open(new_path, 'w', encoding='utf-8') as f:
                    f.write(new_text)
                return new_path
            else:
                # バイナリコピー
                shutil.copy2(template_path, new_path)
                return new_path
        except Exception as exc:
            # フォールバックで画像をコピー
            shutil.copy2(replacement_image_path, new_path)
            return new_path
    else:
        # テンプレートが見つからない -> 画像をコピーして代替ファイルを作る
        shutil.copy2(replacement_image_path, new_path)
        return new_path


def rezip_scp(extracted_root: str, output_scp_path: str) -> None:
    temp_zip_path = output_scp_path + '.tmp'
    with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(extracted_root):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, extracted_root)
                zf.write(full_path, rel_path)
    shutil.move(temp_zip_path, output_scp_path)


def main() -> None:
    parser = argparse.ArgumentParser(description='SCP を解凍して texture URL を読み出し、指定画像で置き換えまたは新規追加した後、SCP を再圧縮します。')
    parser.add_argument('scp_file', help='処理対象の .scp ファイルパス')
    parser.add_argument('--replacement-image', default=os.path.join('output', 'sonolus_particle.png'), help='置き換え元の画像パス (既定: output/sonolus_particle.png)')
    parser.add_argument('--mode', choices=['replace', 'add'], default='replace', help='replace: 既存ファイルを置き換える, add: 新規追加して info を更新する')
    parser.add_argument('--new-name', help='追加モードで作成する新しいアイテムの `name` を指定します（省略可）')
    parser.add_argument('--output-scp', help='再生成する .scp ファイルパス。指定しない場合は元ファイルを上書きします。')

    args = parser.parse_args()
    scp_file = os.path.abspath(args.scp_file)
    replacement_image = os.path.abspath(args.replacement_image)
    mode = args.mode
    new_name = args.new_name
    output_scp = os.path.abspath(args.output_scp) if args.output_scp else scp_file

    if not os.path.isfile(scp_file):
        raise FileNotFoundError(f'.scp ファイルが見つかりません: {scp_file}')

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(scp_file, 'r') as zf:
            safe_extract(zf, temp_dir)

        info_path = find_info_file(temp_dir)
        print(f'使用する info ファイル: {info_path}')

        texture_url = find_texture_url(info_path)
        # テンプレート名を取得（items[0] を使用）
        with open(info_path, 'r', encoding='utf-8') as f:
            info_data_for_template = json.load(f)
        try:
            template_name = info_data_for_template['sections'][0]['items'][0].get('name')
        except Exception:
            template_name = None

        if mode == 'add':
            new_url = add_texture_file(temp_dir, texture_url, replacement_image)
            new_item = add_new_item_to_info(info_path, new_url, new_name=new_name)
            
            # list ファイルも更新
            update_list_file(info_path, new_item, new_url)

            # テンプレートファイルをもとに要素名と同じファイルを作成
            if template_name:
                try:
                    created = create_item_file_from_template(info_path, template_name, new_item.get('name'), replacement_image, new_texture_url=new_url)
                    print(f'テンプレートに基づく要素ファイルを作成しました: {created}')
                except Exception as exc:
                    print(f'テンプレートファイル作成に失敗しました、画像をコピーします: {exc}')
                    item_parent = os.path.dirname(info_path)
                    item_file_path = os.path.join(item_parent, new_item.get('name'))
                    try:
                        shutil.copy2(replacement_image, item_file_path)
                        print(f'要素名と同じファイルを追加しました: {item_file_path}')
                    except Exception as exc2:
                        print(f'要素名ファイルの追加に失敗しました: {exc2}')
            else:
                item_parent = os.path.dirname(info_path)
                item_file_path = os.path.join(item_parent, new_item.get('name'))
                try:
                    shutil.copy2(replacement_image, item_file_path)
                    print(f'要素名と同じファイルを追加しました: {item_file_path}')
                except Exception as exc:
                    print(f'要素名ファイルの追加に失敗しました: {exc}')

            print(f'新規追加した内部ファイル URL: {new_url}')
            print(f'追加した items エントリ name: {new_item.get("name")}')
            print(f'置き換え元画像: {replacement_image}')
        else:
            replaced_path = replace_texture_file(temp_dir, texture_url, replacement_image)
            print(f'置き換えた内部ファイル: {replaced_path}')
            print(f'置き換え元画像: {replacement_image}')

        rezip_scp(temp_dir, output_scp)
        print(f'SCP を再圧縮して保存しました: {output_scp}')


if __name__ == '__main__':
    main()
