# 集成化GIS实时监控系统 - 快速上手指南 (Windows)

本指南旨在帮助您快速配置Python环境，并成功运行本项目的主启动程序 `launch.py`。

## 1. 系统要求

- **操作系统**: Windows 10 / 11
- **必需软件**: Anaconda (或 Miniconda)。

## 2. 环境配置与依赖安装

**目标**: 创建一个名为 `gis_env` 的独立Conda环境，并安装所有必需的库。

---

#### **步骤一：创建并激活Conda环境**

1.  打开 **Anaconda Prompt** (从Windows开始菜单找到它)。

2.  复制并粘贴以下命令，然后按回车。这会创建一个基于Python 3.10的纯净环境：
    ```bash
    conda create -n gis_env python=3.10
    ```
    当提示 `Proceed ([y]/n)?` 时，输入 `y` 并按回车。

3.  创建成功后，使用以下命令激活这个新环境。**后续所有命令都必须在这个已激活的环境中执行**：
    ```bash
    conda activate gis_env
    ```
    成功激活后，您终端的提示符前面会显示 `(gis_env)`。

---

#### **步骤二：安装核心地理空间库 (最关键的一步)**

这些库的依赖关系复杂，必须使用 `conda-forge` 渠道来安装以确保成功。

1.  在已激活的 `(gis_env)` 环境中，运行以下命令：
    ```bash
    conda install -c conda-forge geopandas osmnx
    ```
2.  Conda会计算并列出需要安装的一系列包（包括`numpy`, `pandas`, `shapely`等）。当提示 `Proceed ([y]/n)?` 时，输入 `y` 并按回车。
3.  请耐心等待，这个过程可能会下载和安装大量文件，耗时几分钟。

---

#### **步骤三：安装Web与其他库**

其余的库都是纯Python库，可以使用 `pip` 快速安装。

1.  继续在 `(gis_env)` 环境中，运行以下命令：
    ```bash
    pip install fastapi "uvicorn[standard]" requests pywebview matplotlib folium
    ```
2.  等待所有库安装完成。

**至此，您的运行环境已全部配置完毕！**

## 3. 运行主程序

**前提**:
- 您已经通过 `integrated_trajectory_planner_v4.py` 生成了 `trajectories_master.json` 和 `planned_stations_with_u.csv` 文件，并将它们放在了项目根目录。
- (可选) 您已创建了 `aliases.json` 文件用于定义线路别名。
- 这部分文件内容已经在压缩包里了可以直接跳过

**执行启动**:

1.  打开 **Anaconda Prompt** 并激活环境：
    ```bash
    conda activate gis_env
    ```

2.  使用 `cd` 命令导航到您的项目文件夹。例如：
    ```bash
    cd D:\map
    ```

3.  运行 `launch.py` 脚本：  
    ```bash
    python launch.py
    ```

**预期效果**:
- 终端会显示后台服务启动的日志。
- 约5秒后，一个 **1536x432** 像素的、**无边框**的独立窗口会自动弹出，并显示实时监控界面。

## 4. 关闭程序

- 只需**关闭弹出的应用窗口** (例如，按 `Alt + F4`)，所有后台服务都会被自动、干净地终止。

## 5. launch.py设置

- 这里可以在 `launch.py`里面找到 `DATA_FORWARDER_SCRIPT = ("sim.py" ) #external_simulator.py 换成这个是咱们服务器上读的数据 sim是之前录的数据`可以选择不同的数据源，这里默认是之前录好的vehicles里面的数据
