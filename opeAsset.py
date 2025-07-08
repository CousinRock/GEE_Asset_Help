import ee
import os
from PySide6.QtCore import Qt, QTimer,QRunnable, Slot, QThreadPool
from PySide6.QtWidgets import QTreeView,QMenu, QMessageBox
from PySide6.QtGui import QAction

class MoveAssetTask(QRunnable):
    '''
    移动资产的线程
    '''
    def __init__(self, src_id, dest_folder, asset_type, callback=None):
        super().__init__()
        self.src_id = src_id
        self.dest_folder = dest_folder
        self.asset_type = asset_type
        self.callback = callback  # 可选的完成回调

    @Slot()
    def run(self):
        try:
            print(f"开始移动: {self.src_id} -> {self.dest_folder}")
            self._move_asset(self.src_id, self.dest_folder, self.asset_type)
            print(f"完成: {self.src_id}")
            if self.callback:
                self.callback()
        except Exception as e:
            print(f"移动失败: {e}")

    def _move_asset(self, src_id, dest_folder, asset_type):
        if not dest_folder:
            project = os.environ.get("PROJECT")
            dest_folder = f"projects/{project}/assets"
        if '/' not in src_id:
            project = os.environ.get("PROJECT")
            src_id = f"projects/{project}/assets/{src_id}"

        if asset_type.lower() == 'folder':
            folder_name = src_id.split('/')[-1]
            target_folder = f"{dest_folder}/{folder_name}"
            ee.data.createFolder(target_folder)
            children = ee.data.listAssets({'parent': src_id}).get('assets', [])
            for child in children:
                self._move_asset(child['id'], target_folder, child.get('type', ''))
            ee.data.deleteAsset(src_id)
            return

        name = src_id.split('/')[-1]
        dest_id = f"{dest_folder}/{name}"
        ee.data.renameAsset(src_id, dest_id)

class MyTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dragged_ids = []

    def contextMenuEvent(self, event):
        '''
        文本菜单
        '''
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        item = self.model().itemFromIndex(index)
        asset_info = item.data(Qt.UserRole)

        menu = QMenu(self)

        action_delete = QAction("删除", self)
        action_delete.triggered.connect(lambda: self.delete_asset(asset_info))
        menu.addAction(action_delete)


        menu.exec(event.globalPos())

    def startDrag(self, supportedActions):
        '''
        开始拖拽
        '''
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
        '''
        松开拖拽触发事件
        '''
        super().dropEvent(event)

        # 拖拽结束后延时调用，保证模型结构已更新
        QTimer.singleShot(0, self._processMovedItems)

    def _processMovedItems(self):
        '''
        触发处理程序
        '''
        model = self.model()
        pool = QThreadPool.globalInstance()

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
            return recurse(model.invisibleRootItem())

        for moved_id in self._dragged_ids:
            item = findItemById(moved_id)
            if not item:
                print(f"未找到ID为 {moved_id} 的节点")
                continue

            parent_item = item.parent()
            new_parent_id = parent_item.data(Qt.UserRole).get('id', '') if parent_item else ''

            asset_info = item.data(Qt.UserRole)
            asset_type = asset_info.get('type', '')

            # 启动简化的后台任务
            task = MoveAssetTask(moved_id, new_parent_id, asset_type)
            pool.start(task)

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


# def delete_gee_asset_folder(asset_path):
#     """
#     删除GEE中的资产文件夹及其内容
    
#     参数:
#     asset_path (str): 要删除的资产文件夹路径，例如 'projects/ee-renjiewu660/assets/ShuiHau'
#     """
#     try:
#         # 获取文件夹下的所有资产
#         assets = ee.data.listAssets({'parent': asset_path})['assets']
        
#         # 如果有资产，先删除所有资产
#         if assets:
#             print(f"Found {len(assets)} assets in {asset_path}")
#             for asset in assets:
#                 try:
#                     ee.data.deleteAsset(asset['name'])
#                     print(f"Deleted asset: {asset['name']}")
#                 except Exception as e:
#                     print(f"Error deleting asset {asset['name']}: {str(e)}")
        
#         # 删除文件夹
#         ee.data.deleteAsset(asset_path)
#         print(f"Deleted folder: {asset_path}")
        
#     except Exception as e:
#         print(f"Error: {str(e)}")

# # 使用示例:
# delete_gee_asset_folder('projects/ee-renjiewu660/assets/SH')