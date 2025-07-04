import opeAsset
import setup
from opeAsset import MyTreeView

import sys
from PySide6.QtCore import Qt,QFile, QIODevice, Slot,QEvent
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QMainWindow,QLabel,QTreeView,QHeaderView,QAbstractItemView
from PySide6.QtGui import QFont,QStandardItemModel, QStandardItem


class GEEAssetManager(QMainWindow):
    def __init__(self):
        super().__init__()
        user = setup.initialize_earth_engine()
        # 加载UI文件
        loader = QUiLoader()
        ui_file = QFile("./ui/widget.ui")
        if not ui_file.open(QIODevice.ReadOnly):
            print("无法打开UI文件")
            sys.exit(-1)

        # 加载UI文件并实例化为窗口对象
        self.window = loader.load(ui_file)

        ##调整label
        self.user_label = self.window.findChild(QLabel, "user")
        self.user_label.setText(f"{user}")
        self.user_label.setFont(self.setFont())
        self.user_label.adjustSize()#自适应大小
        ##调整treeview
        old_tree = self.window.findChild(QTreeView, "assets")
        self.asset_tree = MyTreeView(self.window)
        self.asset_tree.setGeometry(old_tree.geometry())  # 保持位置和大小
        self.asset_tree.setStyleSheet(old_tree.styleSheet())  # 保持样式
        old_tree.hide()

        # 关闭UI文件
        ui_file.close()
        self.load_assets()  # 初始化时加载资产

        # 连接选中变化信号
        self.asset_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)# 允许多选
        self.asset_tree.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # 启用拖拽
        self.asset_tree.setDragEnabled(True)
        self.asset_tree.setAcceptDrops(True)
        self.asset_tree.setDropIndicatorShown(True)
        self.asset_tree.setDefaultDropAction(Qt.MoveAction)
        self.asset_tree.setDragDropMode(QAbstractItemView.InternalMove)

    def setFont(self):
        '''
        设置字体样式
        '''
        font = QFont()
        font.setFamily("Arial")       # 字体类型
        font.setPointSize(14)         # 字号
        font.setBold(True)            # 粗体
        # font.setItalic(True)          # 斜体

        return font

    @Slot()
    def on_selection_changed(self, selected, deselected):
        # 获取所有选中的index
        selected_indexes = self.asset_tree.selectionModel().selectedIndexes()
        assets = []
        for index in selected_indexes:
            if index.isValid():
                item = self.asset_tree.model().itemFromIndex(index)
                asset_info = item.data(Qt.UserRole)
                assets.append(asset_info)
        print("选中资产:", assets)


    def load_assets(self):
        '''
        load GEE assets and display in treeview
        '''
        assets = opeAsset.get_assets()
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Assets'])
        
        def insert_asset(asset, parent_item):
            name = asset['id'].split('/')[-1]
            node_text = f"{name} ({asset['type']})"
            item = QStandardItem(node_text)
            item.setData(asset, Qt.UserRole)  # 保存原始资产信息
            parent_item.appendRow(item)
            for child in asset.get('children', []):
                insert_asset(child, item)

        for asset in assets:
            insert_asset(asset, model.invisibleRootItem())
        self.asset_tree.setModel(model)
        # self.asset_tree.expandAll()  # 可选：展开所有节点

        # 设置header不自动拉伸，允许内容超出
        header = self.asset_tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

def display_widget():
    app = QApplication([])
    main_window = GEEAssetManager()
    main_window.window.show()
    app.exec()