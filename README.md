# 北关据点库存查询

多人共用的只读静态桌游库存网站。网站支持按成员、人数、时长、重度、类型、机制、游玩状态及 BGG 数据筛选，可选择 1～5 款桌游并生成竖向分享图片。

每位成员对应 `public/data/inventories/` 中一个 JSON 文件，`hou` 与其他成员使用完全相同的数据格式。公开网页只收录具有有效 BGG ID 的桌游，桌游卡片可直接打开对应的 BGG 页面。

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

## 加入个人库存

普通用户可以在 GitHub 的 Issues 页面选择“加入或更新我的桌游库存”，填写显示名称和 BGG ID 清单。GitHub Action 会读取 BGG 信息、生成个人 JSON、处理封面并更新网页。再次提交会用新清单更新该 GitHub 账号对应的库存。

仓库需要设置 Actions Secret：`BGG_API_TOKEN`，并允许 GitHub Actions 对仓库内容执行写入操作。
