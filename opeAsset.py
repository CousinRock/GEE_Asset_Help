import ee
import geemap
import os
import pandas as pd
import json
import rasterio
import numpy as np
from PySide6.QtCore import Qt, QTimer, QRunnable, Slot, QThreadPool,Signal,QObject
from PySide6.QtWidgets import QTreeView, QMenu, QMessageBox
from PySide6.QtGui import QAction

# --------------------------
# 统一资产操作管理类
# --------------------------
class AssetManager:
    @staticmethod
    def delete(asset_id):
        info = ee.data.getAsset(asset_id)
        asset_type = info.get("type", "")
        if asset_type.lower() == "folder":
            children = ee.data.listAssets({"parent": asset_id}).get("assets", [])
            for child in children:
                AssetManager.delete(child["name"])
        ee.data.deleteAsset(asset_id)
        print(f"✅ 删除资产: {asset_id}")

    @staticmethod
    def move(src_id, dest_folder, asset_type):
        if not dest_folder:
            project = os.environ.get("PROJECT")
            dest_folder = f"projects/{project}/assets"
        if '/' not in src_id:
            project = os.environ.get("PROJECT")
            src_id = f"projects/{project}/assets/{src_id}"

        print(f'{src_id} move to {dest_folder}')

        if asset_type.lower() == 'folder':
            folder_name = src_id.split('/')[-1]
            target_folder = f"{dest_folder}/{folder_name}"
            ee.data.createFolder(target_folder)
            children = ee.data.listAssets({'parent': src_id}).get('assets', [])
            for child in children:
                AssetManager.move(child['id'], target_folder, child.get('type', ''))
            ee.data.deleteAsset(src_id)
        else:
            name = src_id.split('/')[-1]
            dest_id = f"{dest_folder}/{name}"
            ee.data.renameAsset(src_id, dest_id)
        print(f"✅ 移动完成: {src_id} → {dest_folder}")

# --------------------------
# 通用线程任务类
# --------------------------
class AssetTask(QRunnable):
    def __init__(self, func, args=(), callback=None):
        super().__init__()
        self.func = func
        self.args = args
        self.callback = callback

    @Slot()
    def run(self):
        try:
            self.func(*self.args)
            if self.callback:
                self.callback()
        except Exception as e:
            print(f"❌ 任务失败: {e}")

class AssetLoader(QObject):
    finished = Signal(object)
    
class LoadAssetTask(QRunnable):
    def __init__(self):
        super().__init__()
        self.signaler = AssetLoader()

    @Slot()
    def run(self):
        try:
            assets = get_assets()
            self.signaler.finished.emit(assets)
        except Exception as e:
            print(f"❌ 加载资产失败: {e}")

# --------------------------
# 树视图组件
# --------------------------
class MyTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dragged_ids = []

    def removeItemById(self, asset_id):
        model = self.model()

        def recurse_remove(parent):
            for row in range(parent.rowCount()):
                child = parent.child(row)
                if not child:
                    continue
                data = child.data(Qt.UserRole)
                if data and data.get('id') == asset_id:
                    parent.removeRow(row)
                    print(f"🔄 从视图中移除: {asset_id}")
                    return True
                if recurse_remove(child):
                    return True
            return False

        recurse_remove(model.invisibleRootItem())

    def contextMenuEvent(self, event):
        def confirm_and_delete(asset_ids):
            reply = QMessageBox.question(
                self,
                "确认删除",
                "确定要删除以下资产？\n" + "\n".join(asset_ids),
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                pool = QThreadPool.globalInstance()
                for aid in asset_ids:
                    task = AssetTask(
                        AssetManager.delete,
                        args=(aid,),
                        callback=lambda aid=aid: self.removeItemById(aid)
                    )
                    pool.start(task)

        selected_indexes = [i for i in self.selectionModel().selectedIndexes() if i.column() == 0]
        asset_ids = []
        for index in selected_indexes:
            item = self.model().itemFromIndex(index)
            asset_info = item.data(Qt.UserRole)
            if asset_info and 'id' in asset_info:
                asset_ids.append(asset_info['id'])

        if not asset_ids:
            return

        menu = QMenu(self)
        action_delete = QAction("删除", self)
        action_delete.triggered.connect(lambda: confirm_and_delete(asset_ids))
        menu.addAction(action_delete)
        menu.exec(event.globalPos())

    def startDrag(self, supportedActions):
        self._dragged_ids.clear()
        selected_indexes = [i for i in self.selectionModel().selectedIndexes() if i.column() == 0]
        for index in selected_indexes:
            item = self.model().itemFromIndex(index)
            asset_info = item.data(Qt.UserRole)
            if asset_info and 'id' in asset_info:
                self._dragged_ids.append(asset_info['id'])
        super().startDrag(supportedActions)

    def dropEvent(self, event):
        super().dropEvent(event)
        QTimer.singleShot(0, self._processMovedItems)

    def _processMovedItems(self):
        model = self.model()
        pool = QThreadPool.globalInstance()

        def findItemById(asset_id):
            def recurse(parent):
                for row in range(parent.rowCount()):
                    child = parent.child(row)
                    data = child.data(Qt.UserRole)
                    if data and data.get('id') == asset_id:
                        return child
                    result = recurse(child)
                    if result:
                        return result
                return None
            return recurse(model.invisibleRootItem())

        for moved_id in self._dragged_ids:
            item = findItemById(moved_id)
            if not item:
                print(f"未找到 ID: {moved_id}")
                continue
            parent_item = item.parent()
            new_parent_id = parent_item.data(Qt.UserRole).get('id', '') if parent_item else ''
            asset_info = item.data(Qt.UserRole)
            asset_type = asset_info.get('type', '')
            task = AssetTask(AssetManager.move, (moved_id, new_parent_id, asset_type))
            pool.start(task)
            updateItemIdRecursive(item, new_parent_id)
        self._dragged_ids.clear()

# --------------------------
# 递归更新 asset ID
# --------------------------
def updateItemIdRecursive(item, new_parent_id):
    if not new_parent_id:
        project = os.environ.get("PROJECT")
        new_parent_id = f"projects/{project}/assets"
        print(f"⚠️ 使用默认路径: {new_parent_id}")

    asset_info = item.data(Qt.UserRole)
    if not asset_info:
        return
    name = asset_info['id'].split('/')[-1]
    new_id = f"{new_parent_id}/{name}"
    asset_info['id'] = new_id
    item.setData(asset_info, Qt.UserRole)
    for row in range(item.rowCount()):
        child = item.child(row)
        updateItemIdRecursive(child, new_id)

# --------------------------
# 获取 GEE 资产树
# --------------------------
def get_assets():
    def fetch_children(parent_id):
        try:
            children = ee.data.listAssets({'parent': parent_id}).get('assets', [])
            results = []
            for child in children:
                node = {
                    "id": child['id'],
                    "type": child.get('type', ''),
                    "children": []
                }
                if child.get('type', '') == 'Folder':
                    node["children"] = fetch_children(child['id'])
                results.append(node)
            return results
        except Exception as e:
            print(f"❌ 获取子资产失败: {e}")
            return []

    try:
        roots = ee.data.getAssetRoots()
        tree = []
        for root in roots:
            node = {
                "id": root['id'],
                "type": root.get('type', ''),
                "children": fetch_children(root['id'])
            }
            tree.append(node)
        return tree
    except Exception as e:
        print(f"❌ 获取资产根目录失败: {e}")
        return []
    
# 上传文件到asset
def upload_to_asset(file_paths,asset_folder):

    tifs = []
    for i, file_path in enumerate(file_paths[0]):
        file_name = os.path.basename(file_path)
        name_no_ext = os.path.splitext(file_name)[0]
        ext = os.path.splitext(file_path)[1].lower()
        asset_id = f"{asset_folder}/{name_no_ext}"

        print(f"开始上传: {file_path} → {asset_id}")

        try:
            if ext == ".geojson":
                _upload_geojson(file_path=file_path, name_no_ext=name_no_ext,asset_id=asset_id)

            elif ext in ".shp":
                _upload_shp(file_path=file_path, file_name=file_name,asset_id=asset_id)
            elif ext in ".csv":
                _upload_csv(file_path=file_path, file_name=file_name,asset_id=asset_id)
            elif ext in ".tif":
                tifs.append(file_path)

            print(f"✅ 上传任务已启动: {file_name}")
    
        except Exception as e:
            print(f"❌ 上传失败: {file_path} 错误: {e}")

    if tifs:
        _merge_tifs(tifs)


def _upload_geojson(file_path,name_no_ext,asset_id):
    '''
    upload geojson file to GEE
    '''
    with open(file_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
    fc = ee.FeatureCollection([
        ee.Feature(
            ee.Geometry(feature['geometry']),
            {**feature['properties'], 'system:index': str(i)}
        )
        for i, feature in enumerate(geojson_data['features'])
    ])
    task = ee.batch.Export.table.toAsset(
        collection=fc,
        description=f'{name_no_ext}',
        assetId=asset_id
    )
    task.start()

def _upload_shp(file_path,file_name,asset_id):
    '''
    upload shp file to GEE
    '''
    fc = geemap.shp_to_ee(file_path)
    geemap.ee_export_vector_to_asset(fc,description=file_name,assetId=asset_id)

def _upload_csv(file_path,file_name,asset_id):
    '''
    upload csv file to GEE
    '''
    df = pd.read_csv(file_path)
    if not {'longitude', 'latitude'}.issubset(df.columns):
        print(f"❌ CSV 文件中必须包含 'longitude' 和 'latitude' 字段: {file_path}")
        return
    fc = geemap.df_to_ee(df)
    geemap.ee_export_vector_to_asset(fc,description=file_name,assetId=asset_id)

def _merge_tifs(tifs):
    '''
    merge tifs to single tif
    '''
    arrays = []
    profile = None

    for i, path in enumerate(tifs):
        with rasterio.open(path) as src:
            if i == 0:
                profile = src.profile
                height, width = src.height, src.width
            elif src.height != height or src.width != width:
                raise ValueError(f"{path} 的尺寸不一致")
            arrays.append(src.read())  # 多波段读取

    # 拼接成一个大 array: (total_bands, height, width)
    merged = np.concatenate(arrays, axis=0)
    profile.update(count=merged.shape[0])

    # 创建输出目录
    output_dir = './output'
    os.makedirs(output_dir, exist_ok=True)

    # 生成唯一文件名，避免重名
    base_name = 'merged'
    ext = '.tif'
    output_path = os.path.join(output_dir, base_name + ext)
    counter = 1
    
    while os.path.exists(output_path):
        output_path = os.path.join(output_dir, f"{base_name}_{counter}{ext}")
        counter += 1

    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(merged)

    print(f"✅ 合成完成，输出文件: {output_path}")