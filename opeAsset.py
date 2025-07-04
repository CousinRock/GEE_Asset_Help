import ee
import os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QTreeView


class MyTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dragged_ids = []

    def startDrag(self, supportedActions):
        self._dragged_ids.clear()
        model = self.model()

        selected_indexes = [idx for idx in self.selectionModel().selectedIndexes() if idx.column() == 0]
        for index in selected_indexes:
            if not index.isValid():
                continue
            item = model.itemFromIndex(index)
            asset_info = item.data(Qt.UserRole)
            if asset_info and 'id' in asset_info:
                self._dragged_ids.append(asset_info['id'])

        super().startDrag(supportedActions)

    def dropEvent(self, event):
        super().dropEvent(event)

        # 拖拽结束后延时调用，保证模型结构已更新
        QTimer.singleShot(0, self._processMovedItems)

    def _processMovedItems(self):
        model = self.model()

        def findItemById(asset_id):
            def recurse(parent):
                for row in range(parent.rowCount()):
                    child = parent.child(row)
                    if not child:
                        continue
                    data = child.data(Qt.UserRole)
                    if data and data.get('id') == asset_id:
                        return child
                    res = recurse(child)
                    if res:
                        return res
                return None
            root = model.invisibleRootItem()
            return recurse(root)

        for moved_id in self._dragged_ids:
            item = findItemById(moved_id)
            if not item:
                print(f"未找到ID为 {moved_id} 的节点")
                continue

            parent_item = item.parent()
            if parent_item:
                parent_asset = parent_item.data(Qt.UserRole)
                new_parent_id = parent_asset.get('id', '') if parent_asset else ''
            else:
                new_parent_id = ''

             # 从当前节点获取类型
            asset_info = item.data(Qt.UserRole)
            asset_type = asset_info.get('type', '') if asset_info else ''

            print(f"资产 {moved_id} (类型: {asset_type}) 移动到了目录 {new_parent_id}")

            move_asset(moved_id, new_parent_id, asset_type=asset_type)

            # 递归更新节点路径（包含自身和子孙）
            updateItemIdRecursive(item, new_parent_id)

        self._dragged_ids.clear()
        

def get_assets():
    """
    获取用户 Earth Engine 资产的树形结构。
    返回格式示例：
    [
        {
            "id": "root_id",
            "type": "Folder",
            "children": [
                {"id": "child_id", "type": "Folder", "children": [...]},
                {"id": "asset_id", "type": "Image", "children": []}
            ]
        },
        ...
    ]
    """
    def fetch_children(parent_id):
        try:
            children = ee.data.listAssets({'parent': parent_id}).get('assets', [])
            result = []
            for child in children:
                node = {
                    "id": child['id'],
                    "type": child.get('type', ''),
                    "children": []
                }
                if child.get('type', '') == 'Folder':
                    node["children"] = fetch_children(child['id'])
                result.append(node)
            return result
        except Exception as e:
            print(f"Error listing assets for {parent_id}: {e}")
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
        print(tree[0])
        return tree
    except Exception as e:
        print(f"Error retrieving assets: {e}")
        return []


def move_asset(src_id: str, dest_folder: str, asset_type=None):
    '''
    移动资产到新目录。
    如果是文件夹，则递归先移动子资产再移动文件夹自身。
    '''
    try:
        print("正在移动类型",asset_type,"的资产:", src_id, "到目录:", dest_folder)

        # 如果目标目录为空，替换为项目根路径       
        if not dest_folder:     
            project = os.environ.get("PROJECT")
            dest_folder = f"projects/{project}/assets"
            print(f"目标目录为空，使用项目根路径:{dest_folder}")
        
        if '/' not in src_id:
            project = os.environ.get("PROJECT")
            src_id = f"projects/{project}/assets/{src_id}"

        # 如果是文件夹，先递归移动子资产
        if asset_type.lower() == 'folder':
            folder_name = src_id.split('/')[-1]
            ee.data.createFolder(f"{dest_folder}/{folder_name}")  # 确保目标文件夹存在
            children = ee.data.listAssets({'parent': src_id}).get('assets', [])
            for child in children:
                child_id = child['id']
                child_type = child.get('type', '')
                move_asset(child_id, f"{dest_folder}/{src_id.split('/')[-1]}" if dest_folder else src_id.split('/')[-1], asset_type=child_type)
            # 子资产移完后，删除文件夹
            ee.data.deleteAsset(src_id)
            return 
        
        name = src_id.split('/')[-1]
        # 计算目标路径
        if dest_folder:
            dest_id = f"{dest_folder}/{name}"
        else:
            dest_id = name
        print(src_id, "移动到", dest_id)
        ee.data.renameAsset(src_id, dest_id)  
        print(f"成功移动 {src_id} 到 {dest_id}")
    except Exception as e:
        print(f"移动失败: {e}")


def updateItemIdRecursive(item, new_parent_id):
    """
    递归更新 item 及其子节点的 asset id，new_parent_id 是新的父目录路径
    """
    if not new_parent_id:     
        project = os.environ.get("PROJECT")
        new_parent_id = f"projects/{project}/assets"
        print(f"目标目录为空，使用项目根路径:{new_parent_id}")

    asset_info = item.data(Qt.UserRole)
    # print('updateItemIdRecursive',asset_info)
    if not asset_info:
        return
    name = asset_info['id'].split('/')[-1]
    new_id = f"{new_parent_id}/{name}" if new_parent_id else name
    asset_info['id'] = new_id
    print('new',asset_info)
    item.setData(asset_info, Qt.UserRole)
    for row in range(item.rowCount()):
        print('row',row)
        child = item.child(row)
        updateItemIdRecursive(child, new_id)