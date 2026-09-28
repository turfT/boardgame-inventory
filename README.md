# 北关据点库存查询

从 Obsidian 桌游笔记生成的只读静态库存网站。网站支持按人数、时长、重度、类型、机制、游玩状态及 BGG 数据筛选，可选择 1～5 款桌游并生成竖向分享图片。

## 本地预览

```bash
python3 -m http.server 4173
```

打开 `http://localhost:4173/`。

## 更新公开数据

```bash
python3 scripts/export_inventory.py --mode plan
python3 scripts/export_inventory.py --mode write
```

日常更新由 Obsidian 的 QuickAdd 发布命令完成。
