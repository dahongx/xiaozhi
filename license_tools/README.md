# License 生成工具

这是一个独立的许可证生成工具，可以复制到任意设备上使用。

## 目录结构

```
license_tools/
├── license_generator.py    # 主程序
├── README.md               # 说明文档
├── keys/                   # 密钥存储目录（自动生成）
│   ├── private_key.pem     # 私钥（绝对保密！）
│   ├── public_key.pem      # 公钥
│   └── public_key_for_client.txt  # 公钥（方便复制）
└── licenses/               # 生成的许可证目录（自动生成）
    └── license_xxx.lic     # 许可证文件
```

## 依赖安装

```bash
pip install cryptography
```

## 使用方法

### 1. 初始化密钥对（首次使用）

```bash
python license_generator.py --init
```

这会生成 RSA-2048 密钥对，并输出公钥。

**重要**：将公钥复制到客户端程序的 `core/trial_license.py` 中的 `PUBLIC_KEY_PEM` 变量。

### 2. 生成许可证

```bash
# 生成 7 天试用许可证（绑定特定机器）
python license_generator.py --generate --machine-id abc123def456 --days 7

# 生成 30 天通用许可证（任意机器可用）
python license_generator.py --generate --days 30 --licensee "公司A"

# 生成永久企业许可证
python license_generator.py --generate --days 0 --type enterprise --licensee "VIP客户"

# 指定输出路径
python license_generator.py --generate --days 7 --output ./my_license.lic
```

### 3. 其他命令

```bash
# 查看公钥
python license_generator.py --show-public-key

# 列出已生成的许可证
python license_generator.py --list
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--init` | 初始化密钥对 | - |
| `--force` | 强制重新生成密钥对 | - |
| `--generate` | 生成许可证 | - |
| `--machine-id` | 目标机器码，`*` 表示通用 | `*` |
| `--days` | 有效天数，`0` 表示永久 | 7 |
| `--licensee` | 被授权人名称 | Trial User |
| `--type` | 许可证类型（trial/standard/enterprise） | trial |
| `--output` | 输出文件路径 | 自动生成 |
| `--features` | 启用的功能列表 | basic |

## 获取用户机器码

用户需要在客户端运行以下命令获取机器码：

```bash
cd xiaozhi-server
python core/trial_license.py --machine-id
```

然后将机器码发送给管理员。

## 安全提醒

⚠️ **私钥文件 `keys/private_key.pem` 必须严格保密！**

- 不要将此文件夹上传到 Git
- 不要分享给用户
- 建议备份到安全的离线存储

如果私钥泄露，需要重新生成密钥对，所有已发放的许可证将失效。
