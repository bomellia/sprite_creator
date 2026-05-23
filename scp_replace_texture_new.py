import argparse
import copy
import json
import os
import shutil
import tempfile
import uuid
import zipfile

import cv2


def safe_extract(zip_file: zipfile.ZipFile, path: str):

    for member in zip_file.infolist():

        member_path = os.path.normpath(
            os.path.join(path, member.filename)
        )

        abs_root = os.path.abspath(path)
        abs_member = os.path.abspath(member_path)

        if not abs_member.startswith(abs_root):
            raise RuntimeError(
                f'危険なパスを検出: {member.filename}'
            )

        zip_file.extract(member, path)


def load_config(config_path: str):

    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError('config root must be object')

    if 'items' not in data:
        raise ValueError('config.items required')

    if not isinstance(data['items'], list):
        raise ValueError('config.items must be list')

    return data


def find_info_file(extracted_root: str):

    for dirpath, _, filenames in os.walk(extracted_root):

        for filename in filenames:

            if filename != 'info':
                continue

            full_path = os.path.join(
                dirpath,
                filename
            )

            rel = os.path.relpath(
                full_path,
                extracted_root
            ).replace('\\', '/')

            if 'particles' in rel:
                return full_path

    raise FileNotFoundError('info file not found')


def load_info(info_path: str):

    with open(info_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_info(info_path: str, data: dict):

    with open(info_path, 'w', encoding='utf-8') as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write('\n')


def get_all_items(data: dict):

    sections = data.get('sections', [])

    all_items = []

    for section in sections:

        items = section.get('items', [])

        all_items.extend(items)

    return all_items


def find_item_by_name(data: dict, target_name: str):

    items = get_all_items(data)

    for item in items:

        if item.get('name') == target_name:
            return item

    return None


def get_repository_dir(extracted_root: str):

    path = os.path.join(
        extracted_root,
        'sonolus',
        'repository'
    )

    os.makedirs(path, exist_ok=True)

    return path


def create_repository_object(
    extracted_root: str,
    source_file: str
):

    if not os.path.isfile(source_file):
        raise FileNotFoundError(source_file)

    repository_dir = get_repository_dir(
        extracted_root
    )

    hash_name = uuid.uuid4().hex

    destination = os.path.join(
        repository_dir,
        hash_name
    )

    shutil.copy2(
        source_file,
        destination
    )

    return {
        'hash': hash_name,
        'url': f'/sonolus/repository/{hash_name}'
    }


def create_thumbnail_object(
    extracted_root: str,
    thumbnail_path: str
):

    image = cv2.imread(
        thumbnail_path,
        cv2.IMREAD_UNCHANGED
    )

    if image is None:
        raise RuntimeError(
            f'thumbnail load failed: {thumbnail_path}'
        )

    image = cv2.resize(
        image,
        (400, 400),
        interpolation=cv2.INTER_AREA
    )

    temp_path = thumbnail_path + '.tmp.png'

    cv2.imwrite(temp_path, image)

    try:

        return create_repository_object(
            extracted_root,
            temp_path
        )

    finally:

        if os.path.exists(temp_path):
            os.remove(temp_path)


def overwrite_item(
    extracted_root: str,
    item: dict,
    item_config: dict,
    info_data: dict
):
    apply_metadata_overrides(
        item,
        item_config,
        info_data
    )

    texture_path = item_config.get('texture')

    if texture_path:

        item['texture'] = create_repository_object(
            extracted_root,
            texture_path
        )

        print(
            f'texture updated: {item["name"]}'
        )

    thumbnail_path = item_config.get('thumbnail')

    if thumbnail_path:

        item['thumbnail'] = create_thumbnail_object(
            extracted_root,
            thumbnail_path
        )

        print(
            f'thumbnail updated: {item["name"]}'
        )


def clone_item(
    extracted_root: str,
    data: dict,
    template_name: str,
    item_config: dict
):

    template = find_item_by_name(
        data,
        template_name
    )

    if template is None:
        raise ValueError(
            f'template not found: {template_name}'
        )

    new_item = copy.deepcopy(template)

    target_name = item_config['target_name']

    new_item['name'] = target_name

    texture_path = item_config.get('texture')

    if texture_path:

        new_item['texture'] = create_repository_object(
            extracted_root,
            texture_path
        )

    thumbnail_path = item_config.get('thumbnail')

    if thumbnail_path:

        new_item['thumbnail'] = create_thumbnail_object(
            extracted_root,
            thumbnail_path
        )

    sections = data['sections']

    if len(sections) == 0:
        raise ValueError('sections empty')

    sections[0]['items'].append(new_item)

    apply_metadata_overrides(
        new_item,
        item_config,
        data
    )

    print(f'created new item: {target_name}')


def process_item(
    extracted_root: str,
    data: dict,
    template_name: str,
    item_config: dict
):

    target_name = item_config['target_name']

    existing = find_item_by_name(
        data,
        target_name
    )

    if existing:

        overwrite_item(
            extracted_root,
            existing,
            item_config,
            data
        )

    else:

        clone_item(
            extracted_root,
            data,
            template_name,
            item_config
        )
    
    create_item_detail_file(
        extracted_root,
        existing if existing else find_item_by_name(
            data,
            target_name
        ),
        template_name
    )

def find_root_info_file(extracted_root: str):

    candidate = os.path.join(
        extracted_root,
        'sonolus',
        'info'
    )

    if not os.path.exists(candidate):
        return None

    return candidate


def update_root_info(
    extracted_root: str,
    config: dict
):

    root_info_path = find_root_info_file(
        extracted_root
    )

    if root_info_path is None:
        return

    with open(
        root_info_path,
        'r',
        encoding='utf-8'
    ) as f:

        data = json.load(f)

    if 'root_title' in config:

        data['title'] = config['root_title']

        print(
            f'root title updated: {config["root_title"]}'
        )

    with open(
        root_info_path,
        'w',
        encoding='utf-8'
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write('\n')

def apply_metadata_overrides(
    item: dict,
    item_config: dict,
    info_data: dict
):

    #
    # 基本メタデータ上書き
    #

    for key in [
        'source',
        'title',
        'subtitle',
        'author'
    ]:

        if key in item_config:
            item[key] = item_config[key]

    #
    # authorUser 自動補完
    #

    if 'author' in item_config:

        target_author = item_config['author']

        matched_author_user = None

        for candidate in get_all_items(info_data):

            if candidate.get('author') == target_author:

                author_user = candidate.get(
                    'authorUser'
                )

                if isinstance(author_user, dict):

                    matched_author_user = copy.deepcopy(
                        author_user
                    )

                    break

        if matched_author_user is not None:

            item['authorUser'] = matched_author_user

            print(
                f'authorUser copied from existing author: {target_author}'
            )

        else:

            print(
                f'warning: authorUser source not found for {target_author}'
            )

def find_list_file(extracted_root: str):

    for dirpath, _, filenames in os.walk(extracted_root):

        for filename in filenames:

            if filename != 'list':
                continue

            full_path = os.path.join(
                dirpath,
                filename
            )

            rel = os.path.relpath(
                full_path,
                extracted_root
            ).replace('\\', '/')

            if 'particles' in rel:
                return full_path

    return None


def load_json_file(path: str):

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(path: str, data):

    with open(path, 'w', encoding='utf-8') as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write('\n')


def update_list_item(
    list_data: dict,
    item: dict
):

    items = list_data.get('items')

    if not isinstance(items, list):
        raise ValueError('list.items invalid')

    target_name = item['name']

    existing = None

    for x in items:

        if x.get('name') == target_name:
            existing = x
            break

    if existing is not None:

        existing.clear()
        existing.update(
            copy.deepcopy(item)
        )

        print(
            f'list updated: {target_name}'
        )

    else:

        items.append(
            copy.deepcopy(item)
        )

        print(
            f'list appended: {target_name}'
        )


def sync_list_file(
    extracted_root: str,
    info_data: dict
):

    list_path = find_list_file(
        extracted_root
    )

    if list_path is None:

        print('list file not found')
        return

    list_data = load_json_file(
        list_path
    )

    info_items = get_all_items(
        info_data
    )

    for item in info_items:

        update_list_item(
            list_data,
            item
        )

    save_json_file(
        list_path,
        list_data
    )

    print(f'list synced: {list_path}')


def rezip_scp(
    extracted_root: str,
    output_scp: str
):

    os.makedirs(
        os.path.dirname(output_scp),
        exist_ok=True
    )

    temp_zip = output_scp + '.tmp'

    with zipfile.ZipFile(
        temp_zip,
        'w',
        zipfile.ZIP_DEFLATED
    ) as zf:

        for dirpath, _, filenames in os.walk(
            extracted_root
        ):

            for filename in filenames:

                full_path = os.path.join(
                    dirpath,
                    filename
                )

                rel_path = os.path.relpath(
                    full_path,
                    extracted_root
                )

                zf.write(
                    full_path,
                    rel_path
                )

    shutil.move(
        temp_zip,
        output_scp
    )

def get_particles_dir(extracted_root: str):

    path = os.path.join(
        extracted_root,
        'sonolus',
        'particles'
    )

    if not os.path.isdir(path):
        raise FileNotFoundError(
            f'particles dir not found: {path}'
        )

    return path


def create_item_detail_file(
    extracted_root: str,
    item: dict,
    template_name: str
):

    particles_dir = get_particles_dir(
        extracted_root
    )

    template_path = os.path.join(
        particles_dir,
        template_name
    )

    output_path = os.path.join(
        particles_dir,
        item['name']
    )

    if not os.path.exists(template_path):
        raise FileNotFoundError(
            f'template item file not found: {template_path}'
        )

    with open(
        template_path,
        'r',
        encoding='utf-8'
    ) as f:

        template_data = json.load(f)

    template_data['item'] = copy.deepcopy(item)

    with open(
        output_path,
        'w',
        encoding='utf-8'
    ) as f:

        json.dump(
            template_data,
            f,
            ensure_ascii=False,
            indent=4
        )

        f.write('\n')

    print(
        f'item detail file updated: {output_path}'
    )

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        'scp_file'
    )

    parser.add_argument(
        '--config',
        required=True
    )

    args = parser.parse_args()

    scp_file = os.path.abspath(
        args.scp_file
    )

    config = load_config(
        args.config
    )

    output_scp = os.path.abspath(
        config.get(
            'output_scp',
            'output/output.scp'
        )
    )

    template_name = config.get(
        'template_name'
    )

    if not template_name:
        raise ValueError(
            'template_name required'
        )

    with tempfile.TemporaryDirectory() as temp_dir:

        with zipfile.ZipFile(
            scp_file,
            'r'
        ) as zf:

            safe_extract(
                zf,
                temp_dir
            )

        info_path = find_info_file(
            temp_dir
        )

        print(f'info: {info_path}')

        data = load_info(info_path)

        for item_config in config['items']:

            process_item(
                temp_dir,
                data,
                template_name,
                item_config
            )

        update_root_info(
            temp_dir,
            config
        )

        save_info(
            info_path,
            data
        )

        sync_list_file(
            temp_dir,
            data
        )

        rezip_scp(
            temp_dir,
            output_scp
        )

        print(
            f'saved: {output_scp}'
        )


if __name__ == '__main__':
    main()