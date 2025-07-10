import opeAsset
import setup
from opeAsset import MyTreeView,LoadAssetTask

import sys
import os
from PySide6.QtCore import Qt,QFile, QIODevice, Slot,QThreadPool
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QMainWindow,QLabel,QTreeView,QHeaderView,QAbstractItemView,QPushButton,QProgressDialog,QFileDialog,QMessageBox
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
        ##刷新按钮
        self.refresh_btn = self.window.findChild(QPushButton,'refresh')       
        self.refresh_btn.clicked.connect(self.reload_assets_async)#连接刷新按钮
        ##上传按钮
        self.upload_btn = self.window.findChild(QPushButton,'upload')
        self.upload_btn.clicked.connect(self.handle_upload)


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

    def reload_assets_async(self):
        '''
        异步刷新资产树
        '''
        # 显示加载中提示
        self.loading_dialog = QProgressDialog("刷新中.....",None,0,0,self)
        self.loading_dialog.setWindowTitle("请稍候")
        self.loading_dialog.setWindowModality(Qt.ApplicationModal)
        self.loading_dialog.setCancelButton(None)
        self.loading_dialog.setStyleSheet("""
            QProgressBar {
                text-align: center;
            }
        """)

        self.loading_dialog.show()

        # 创建任务
        task = LoadAssetTask()
        task.signaler.finished.connect(self.on_assets_loaded)  # 在主线程调用
        QThreadPool.globalInstance().start(task)

    @Slot()
    def handle_upload(self):
        # 1. 获取用户选择的资产目标文件夹
        selected_indexes = self.asset_tree.selectionModel().selectedIndexes()
        selected_folder = None

        for index in selected_indexes:
            if index.column() != 0:
                continue
            item = self.asset_tree.model().itemFromIndex(index)
            asset_info = item.data(Qt.UserRole)
            if asset_info.get("type") == "Folder":
                selected_folder = asset_info['id']
                break  

        if not selected_folder:
            QMessageBox.warning(self, "未选择目标文件夹", "请选择目标文件夹后再上传。")
            return

        # 2. 打开文件选择对话框
        file_paths = QFileDialog.getOpenFileNames(
            self, 
            "选择上传文件", 
            "", 
            "(*.geojson *.shp *.csv);;所有文件 (*)"
        )

        if file_paths:  # file_paths 是 (list, filter)
            # 显示加载中提示
            self.loading_dialog = QProgressDialog(self)
            self.loading_dialog.setWindowTitle("请稍候")
            self.loading_dialog.setWindowModality(Qt.ApplicationModal)
            self.loading_dialog.setCancelButton(None)
            self.loading_dialog.show()
            print(f"📂 上传到: {selected_folder}")
            print(f"📄 文件列表: {file_paths[0]}")
            opeAsset.upload_to_asset(file_paths, selected_folder)
            # 关闭提示框
            if self.loading_dialog:
                self.loading_dialog.close()
                self.loading_dialog = None

    @Slot(object)
    def on_assets_loaded(self, assets):
        '''
        加载资产触发
        '''
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Assets'])

        def insert_asset(asset, parent_item):
            name = asset['id'].split('/')[-1]
            node_text = f"{name} ({asset['type']})"
            item = QStandardItem(node_text)
            item.setData(asset, Qt.UserRole)
            parent_item.appendRow(item)
            for child in asset.get('children', []):
                insert_asset(child, item)

        for asset in assets:
            insert_asset(asset, model.invisibleRootItem())

        self.asset_tree.setModel(model)
        header = self.asset_tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)

        # 关闭提示框
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None

    @Slot()
    def on_selection_changed(self):
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