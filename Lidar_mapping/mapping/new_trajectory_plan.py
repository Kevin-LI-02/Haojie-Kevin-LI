# ==============================================================================
# 文件名: integrated_trajectory_planner_v3.py
# 描述: 一个集成的3D RTK轨迹处理与交互式站点规划工具。
#
# 版本 3 更新:
# - 新增了将B样条参数导出为C++友好的JSON格式的功能。
# - `process_txt_to_npz` 重命名为 `process_txt_to_spline_data`，
#   现在会同时生成 .npz 文件 (用于Python内部流程) 和 trajectory.json 文件 (用于外部C++项目)。
# ==============================================================================

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev
from pyproj import CRS, Transformer
import folium
import geopandas as gpd
import osmnx as ox
from shapely.geometry import LineString, box
import branca.element
import json


# ==============================================================================
# 模块 0: 环境配置 (无变动)
# ==============================================================================

def setup_environment_variables():
    """设置GDAL和PROJ的环境变量，以解决某些环境下的CRS加载问题。"""
    try:
        env_prefix = sys.prefix
        gdal_data_path = os.path.join(env_prefix, 'Library', 'share', 'gdal')
        proj_lib_path = os.path.join(env_prefix, 'Library', 'share', 'proj')
        if os.path.exists(gdal_data_path):
            os.environ['GDAL_DATA'] = gdal_data_path
            print("✅ 环境配置: GDAL_DATA 环境变量已设置。")
        if os.path.exists(proj_lib_path):
            os.environ['PROJ_LIB'] = proj_lib_path
            print("✅ 环境配置: PROJ_LIB 环境变量已设置。")
    except Exception:
        print("ℹ️ 未能自动设置GDAL/PROJ环境变量，若坐标转换失败请手动配置。")
        pass


# ==============================================================================
# 模块 1: TXT文件处理与3D样条拟合 (新增JSON导出函数)
# ==============================================================================

def convert_gps_to_normalized_utm_3d(
        input_txt_path: str,
        lat_col: str = 'dLatitude',
        lon_col: str = 'dLongitude',
        alt_col: str = 'fAltitude',
        verbose: bool = True,
):
    """读取GPS txt文件，转换为归一化的UTM坐标(X,Y,Z)，并返回处理后的点和原点。"""
    if verbose:
        print(f"➡️ [步骤 1/5] 正在读取文件: {input_txt_path}")
    try:
        df = pd.read_csv(input_txt_path, sep=r'\s+', engine='python')
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return None, None, None

    required_cols = [lat_col, lon_col, alt_col]
    if not all(col in df.columns for col in required_cols):
        print(f"❌ 找不到指定的经纬高列: {required_cols}")
        print(f"    文件中可用的列: {list(df.columns)}")
        return None, None, None

    df_clean = df.dropna(subset=required_cols).copy()
    if verbose:
        print(f"ℹ️ 丢弃无效行后，剩余行数: {len(df_clean)}")

    if df_clean.empty:
        print("❌ 清洗后无有效数据。")
        return None, None, None

    lats = df_clean[lat_col].astype(float).values
    lons = df_clean[lon_col].astype(float).values
    alts = df_clean[alt_col].astype(float).values

    first_lon, first_lat = lons[0], lats[0]
    utm_zone = int((first_lon + 180) / 6) + 1
    epsg_code = 32600 + utm_zone if first_lat >= 0 else 32700 + utm_zone
    if verbose:
        print(f"ℹ️ 检测到坐标系: UTM带={utm_zone}, EPSG:{epsg_code}")

    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg_code}", always_xy=True)
    utm_x, utm_y = transformer.transform(lons, lats)

    origin = np.array([utm_x[0], utm_y[0], alts[0]])
    if verbose:
        print(f"🌍 [步骤 2/5] 坐标已归一化，绝对坐标原点 (Origin) 为: {origin}")

    x_norm = utm_x - origin[0]
    y_norm = utm_y - origin[1]
    z_norm = alts - origin[2]

    normalized_points = np.vstack((x_norm, y_norm, z_norm)).T
    return normalized_points, origin, f"EPSG:{epsg_code}"


def remove_consecutive_duplicates_3d(points):
    """移除与前一个点坐标完全相同的连续重复3D点。"""
    if len(points) == 0:
        return points

    print(f"🧹 [步骤 3/5] 正在移除连续的重复坐标点...")
    kept_points = [points[0]]
    for i in range(1, len(points)):
        if not np.array_equal(points[i], points[i - 1]):
            kept_points.append(points[i])

    discarded_count = len(points) - len(kept_points)
    print(f"ℹ️ 从 {len(points)} 个点中移除了 {discarded_count} 个连续重复点，剩余 {len(kept_points)} 个点。")
    return np.array(kept_points)


def save_spline_tck_with_origin(filename, tck, origin, epsg):
    """将B样条的tck、坐标原点和EPSG代码保存到.npz文件中。"""
    t, c, k = tck
    np.savez_compressed(filename, t=t, c=c, k=k, origin=origin, epsg=epsg)
    print(f"💾 [步骤 5a/5] 样条参数(NPZ)已保存至: {filename}")


# <<< --- 新增函数 --- >>>
def save_spline_to_json(filename, tck, origin, epsg):
    """
    将B样条的tck参数、坐标原点和EPSG代码保存到JSON文件中。
    """
    t, c, k = tck

    # 注意: c (控制点) 需要转置为 N x 3 的格式，以便于在C++中处理。
    # 原始的c是3 x N的，表示 [x_coords, y_coords, z_coords]
    control_points_transposed = np.asarray(c).T.tolist()

    json_data = {
        "knots": np.asarray(t).tolist(),
        "control_points": control_points_transposed,
        "degree": int(k),
        "origin": np.asarray(origin).tolist(),
        "epsg_code": epsg
    }

    try:
        with open(filename, 'w') as f:
            json.dump(json_data, f, indent=4)
        print(f"💾 [步骤 5b/5] 样条参数(JSON)已成功保存至: {filename}")
    except Exception as e:
        print(f"❌ 保存JSON文件失败: {e}")


# <<< --- 新增结束 --- >>>

def plot_normalized_spline_fit_3d(points, tck, title="3D Spline Fit"):
    """绘制3D原始点和拟合后的B样条曲线，Z轴视野固定在[-0.5, 0.5]米。"""
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    max_points_to_display = 2000
    num_total_points = len(points)
    if num_total_points > max_points_to_display:
        step = num_total_points // max_points_to_display
        points_to_plot = points[::step]
        label_text = f'去重后的点 (抽样显示 {len(points_to_plot)}/{num_total_points} 个)'
    else:
        points_to_plot = points
        label_text = f'去重后的点 ({num_total_points} 个)'

    ax.scatter(points_to_plot[:, 0], points_to_plot[:, 1], points_to_plot[:, 2],
               c='red', marker='.', s=10, label=label_text, alpha=0.7)

    u_fine = np.linspace(0, 1, num=1000)
    x_fit, y_fit, z_fit = splev(u_fine, tck)
    ax.plot(x_fit, y_fit, z_fit, 'blue', lw=2, label='B样条拟合曲线')

    ax.set_xlabel('X 相对位移 (m)')
    ax.set_ylabel('Y 相对位移 (m)')
    ax.set_zlabel('Z 相对位移 (m)')
    ax.set_title(title, fontsize=16)
    ax.legend()
    ax.grid(True)
    ax.set_zlim(-0.5, 0.5)

    print("✅ Z轴显示范围已固定为 [-0.5, 0.5] 米。X和Y轴将自动缩放以显示此范围内的轨迹。")
    print("⚠️ 警告：如果轨迹的Z值完全不在此范围内，绘图区将为空。")
    print("📈 显示3D绘图预览。关闭绘图窗口即可继续下一步。")
    plt.show()


# ==============================================================================
# 模块 2: 地图可视化与站点规划 (无变动)
# ==============================================================================

def visualize_and_pick_stations_html(npz_file_path: str):
    """加载.npz文件，生成并打开一个交互式Folium地图用于站点规划。"""
    print("\n--- 开始生成交互式规划地图 ---")
    data = np.load(npz_file_path)
    tck = (data['t'], data['c'], data['k'])
    origin = data['origin']
    source_utm_epsg = str(data['epsg'])

    num_points = 20001
    print(f"✅ 正在从样条生成高密度轨迹 ({num_points} 个点)...")
    u_fine = np.linspace(0, 1, num=num_points)

    normalized_points = np.array(splev(u_fine, tck)).T
    absolute_utm_points = normalized_points + origin

    print(f"🗺️ 正在将轨迹从 {source_utm_epsg} 转换回 WGS84 经纬度...")
    target_wgs84_epsg = "EPSG:4326"
    to_wgs84 = Transformer.from_crs(source_utm_epsg, target_wgs84_epsg, always_xy=True)
    lons, lats = to_wgs84.transform(absolute_utm_points[:, 0], absolute_utm_points[:, 1])
    path_points_latlon = list(zip(lats, lons))

    # GIS地块分析 (使用缓冲区域优化查询范围)
    gdf_ring1, gdf_ring2 = None, None
    try:
        print("🏠 正在准备从OpenStreetMap获取附近的建筑物地块...")
        # 1. 在UTM坐标系下创建轨迹线
        trajectory_line_utm = LineString(absolute_utm_points[:, :2])

        # 2. 创建一个50米的缓冲区
        buffer_distance_meters = 50
        trajectory_buffer_utm = trajectory_line_utm.buffer(buffer_distance_meters)

        # 3. 获取缓冲区的边界框 (BBox)
        bbox_utm = trajectory_buffer_utm.bounds

        # 4. 将UTM边界框转换回WGS84经纬度，用于OSMnx查询
        to_wgs84_bbox = Transformer.from_crs(source_utm_epsg, target_wgs84_epsg, always_xy=True)
        west, east = to_wgs84_bbox.transform([bbox_utm[0], bbox_utm[2]], [bbox_utm[1], bbox_utm[3]])
        query_bbox = (max(lats), min(lats), max(lons), min(lons))  # north, south, east, west

        print(f"✅ 已将查询区域优化为轨迹周围 {buffer_distance_meters} 米范围，开始获取数据...")

        # 5. 使用优化后的、更小的边界框进行查询
        gdf_buildings = ox.features.features_from_bbox(bbox=query_bbox, tags={"building": True})

        # 6. 后续处理与之前类似，但在更少的数据上进行，速度更快
        if not gdf_buildings.empty:
            gdf_buildings_utm = gdf_buildings.to_crs(source_utm_epsg)
            indices_ring1 = gdf_buildings_utm.geometry.intersects(trajectory_buffer_utm)
            gdf_ring1 = gdf_buildings_utm[indices_ring1].to_crs(target_wgs84_epsg)

            if not gdf_ring1.empty:
                ring1_union_geom = gdf_buildings_utm[indices_ring1].unary_union
                indices_touching_ring1 = gdf_buildings_utm.geometry.touches(ring1_union_geom)
                gdf_ring2 = gdf_buildings_utm[indices_touching_ring1 & ~indices_ring1].to_crs(target_wgs84_epsg)

        print("✅ 成功加载并分析了建筑物地块。")
    except Exception as e:
        print(f"⚠️ GIS地块分析失败 (可能是网络问题或区域内无数据): {e}。将继续不显示地块。")

    # 创建Folium地图 (无变动)
    map_center = [np.mean(lats), np.mean(lons)]
    m = folium.Map(location=map_center, zoom_start=19, tiles=None)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Esri Satellite', max_zoom=19).add_to(m)

    if gdf_ring2 is not None and not gdf_ring2.empty:
        folium.GeoJson(gdf_ring2.to_json(), name='第二圈地块',
                       style_function=lambda x: {'fillColor': 'gray', 'color': 'white', 'weight': 0.5,
                                                 'fillOpacity': 0.4}).add_to(m)
    if gdf_ring1 is not None and not gdf_ring1.empty:
        folium.GeoJson(gdf_ring1.to_json(), name='第一圈地块',
                       style_function=lambda x: {'fillColor': 'yellow', 'color': 'k', 'weight': 1,
                                                 'fillOpacity': 0.6}).add_to(m)

    folium.PolyLine(locations=path_points_latlon, color='cyan', weight=5, tooltip="期望轨迹").add_to(m)
    folium.Marker(location=path_points_latlon[0], popup="起点", icon=folium.Icon(color='green', icon='play')).add_to(m)
    folium.Marker(location=path_points_latlon[-1], popup="终点", icon=folium.Icon(color='red', icon='stop')).add_to(m)

    # 注入HTML和JavaScript控制面板 (无变动)
    control_panel_html = """
    <div style="position: fixed; top: 10px; right: 10px; z-index:1000; background-color: rgba(255, 255, 255, 0.9); border: 2px solid grey; border-radius: 5px; padding: 10px; font-family: sans-serif; width: 220px;">
        <h4>站点规划控制台</h4>
        <label for="u_slider">通过滑块控制:</label>
        <input type="range" id="u_slider" min="0" max="10000" value="0" style="width: 100%;">
        <label for="u_input">手动输入 U 值 (完成后按回车):</label>
        <input type="number" id="u_input" min="0" max="1" step="0.0001" value="0" style="width: 100%; margin-bottom: 10px;">
        <p style="margin: 5px 0;">当前 U 值: <strong id="u_display">0.0000</strong></p>
        <button id="add_station_btn" style="width: 100%; padding: 8px; background-color: #007BFF; color: white; border: none; border-radius: 3px; cursor: pointer; margin-bottom: 10px;">添加站点到当前位置</button>
        <hr>
        <button onclick="exportStations()" style="width: 100%; padding: 8px; background-color: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">导出所有站点 (CSV)</button>
        <p id="station_count" style="text-align: center; margin-top: 5px;">已添加: 0 个站点</p>
    </div>
    """

    trajectory_data_for_js = [{'lat': lat, 'lng': lon, 'u': u} for (lat, lon), u in zip(path_points_latlon, u_fine)]
    trajectory_json = json.dumps(trajectory_data_for_js)

    js_logic = f"""
    <script>
        var stations = [];
        var trajectoryPoints = {trajectory_json};
        var map_obj = null;
        var previewMarker = null;
        var isInputFocused = false;

        function updatePreviewFromU(u) {{
            u = Math.max(0, Math.min(1, u));
            let index = Math.round(u * (trajectoryPoints.length - 1));
            let point = trajectoryPoints[index];
            if (previewMarker) {{
                previewMarker.setLatLng([point.lat, point.lng]);
            }}
            let real_u = point.u;
            document.getElementById('u_slider').value = real_u * 10000;
            document.getElementById('u_input').value = real_u.toFixed(4);
            document.getElementById('u_display').innerText = real_u.toFixed(4);
        }}

        function updatePreviewFromMouse(lat, lng) {{
            let minDistanceSq = Infinity;
            let closestPoint = null;
            trajectoryPoints.forEach(function(point) {{
                let distSq = Math.pow(point.lat - lat, 2) + Math.pow(point.lng - lng, 2);
                if (distSq < minDistanceSq) {{ minDistanceSq = distSq; closestPoint = point; }}
            }});
            if (closestPoint) {{
                updatePreviewFromU(closestPoint.u);
            }}
        }}

        function addStation() {{
            let currentU = parseFloat(document.getElementById('u_input').value);
            if (isNaN(currentU)) return;
            let index = Math.round(currentU * (trajectoryPoints.length - 1));
            let point = trajectoryPoints[index];
            let defaultName = "站点 " + (stations.length + 1);
            let stationName = prompt("请输入站点名称：", defaultName);
            if (stationName === null || stationName.trim() === '') return;
            stations.push({{ lat: point.lat, lng: point.lng, name: stationName, u: point.u }});
            L.marker([point.lat, point.lng], {{draggable: false}}).addTo(map_obj).bindPopup("<b>" + stationName + "</b><br>u = " + point.u.toFixed(4));
            document.getElementById('station_count').innerText = "已添加: " + stations.length + " 个站点";
        }}

        function exportStations() {{
            if (stations.length === 0) {{ alert("您还没有添加任何站点！"); return; }}
            let header = "station_id,name,latitude,longitude,u_parameter\\n";
            let csvRows = stations.map((station, index) => {{
                let stationName = '"' + station.name.replace(/"/g, '""') + '"';
                return [(index + 1), stationName, station.lat, station.lng, station.u.toFixed(6)].join(',');
            }});
            let csvContent = "\\uFEFF" + header + csvRows.join("\\n");
            var blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            var link = document.createElement("a");
            var url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", "planned_stations_with_u.csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}

        setTimeout(function() {{
            map_obj = {m.get_name()};
            previewMarker = L.circleMarker([0,0], {{ radius: 8, color: 'blue', weight: 2, fillColor: 'cyan', fillOpacity: 0.5, dashArray: '5, 5' }}).addTo(map_obj);
            previewMarker.bindTooltip("预览位置");

            document.getElementById('u_slider').addEventListener('input', function() {{ updatePreviewFromU(parseFloat(this.value) / 10000); }});
            let uInput = document.getElementById('u_input');
            uInput.addEventListener('change', function() {{ let u = parseFloat(this.value); if (!isNaN(u)) updatePreviewFromU(u); }});
            uInput.addEventListener('focus', function() {{ isInputFocused = true; }});
            uInput.addEventListener('blur', function() {{ isInputFocused = false; }});
            map_obj.on('mousemove', function(e) {{ if (!isInputFocused) updatePreviewFromMouse(e.latlng.lat, e.latlng.lng); }});
            document.getElementById('add_station_btn').addEventListener('click', addStation);

            updatePreviewFromU(0);
        }}, 500);
    </script>
    """

    m.get_root().html.add_child(branca.element.Element(control_panel_html))
    m.get_root().html.add_child(branca.element.Element(js_logic))
    folium.LayerControl().add_to(m)

    output_html = os.path.splitext(npz_file_path)[0] + '_interactive_planner.html'
    m.save(output_html)
    print(f"\n🎉 交互式规划地图已生成: {output_html}")

    try:
        os.startfile(output_html)
        print("✅ 正在默认浏览器中打开地图...")
    except AttributeError:
        os.system(f'{"open" if sys.platform == "darwin" else "xdg-open"} "{output_html}"')
        print(f"✅ 尝试在系统中打开地图: {output_html}")


# ==============================================================================
# 模块 3: 工作流与主GUI (逻辑修改)
# ==============================================================================

# <<< --- 函数已重命名并修改 --- >>>
def process_txt_to_spline_data(input_file):
    """主处理流程，成功时返回 .npz 文件路径, 失败时返回 None。"""
    normalized_points, origin, epsg_code = convert_gps_to_normalized_utm_3d(input_file, verbose=True)
    if normalized_points is None:
        messagebox.showerror("预处理失败", "未能生成归一化的UTM坐标。请检查控制台输出。")
        return None

    unique_points = remove_consecutive_duplicates_3d(normalized_points)
    if len(unique_points) < 4:
        messagebox.showerror("数据不足", f"移除重复点后数据点不足({len(unique_points)})。B样条拟合需要至少4个点。")
        return None

    try:
        spline_tck, _ = splprep(unique_points.T, s=20.0, k=3)
        print("📌 [步骤 4/5] 成功拟合3D B样条曲线。")
    except Exception as e:
        messagebox.showerror("样条拟合错误", f"拟合过程中发生错误: \n{e}")
        return None

    # 保存数据 (双重输出)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_dir = os.path.dirname(input_file)

    # 1. 保存.npz文件，供Python内部流程使用
    npz_name = os.path.join(output_dir, base_name + '_spline.npz')
    save_spline_tck_with_origin(npz_name, spline_tck, origin, epsg_code)

    # 2. 新增: 保存JSON文件，这是C++项目需要的
    json_name = os.path.join(output_dir, 'trajectory.json')
    save_spline_to_json(json_name, spline_tck, origin, epsg_code)

    # 3D绘图预览逻辑
    try:
        plt.rcParams['font.family'] = 'SimHei'
        plt.rcParams['axes.unicode_minus'] = False
        plot_title = f"文件'{os.path.basename(input_file)}'的3D样条拟合预览"
        plot_normalized_spline_fit_3d(unique_points, spline_tck, title=plot_title)
    except Exception as e:
        messagebox.showwarning("绘图警告", f"3D绘图预览失败，但这不影响后续的地图规划。\n错误: {e}")

    # 更新弹窗消息
    messagebox.showinfo("步骤 1/2 完成",
                        f"3D样条处理成功！\n\n样条数据已保存到:\n{npz_name}\n和\n{json_name}\n\n接下来将自动打开地图规划界面。")
    return npz_name


def start_workflow_from_txt():
    """工作流1: 引导用户从 TXT 文件开始，完成整个流程。"""
    txt_path = filedialog.askopenfilename(
        title="第 1 步: 选择一个RTK TXT数据文件",
        filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
    )
    if not txt_path:
        messagebox.showinfo("操作取消", "用户已取消选择文件。")
        return

    try:
        # <<< --- 调用已更新的函数 --- >>>
        npz_path = process_txt_to_spline_data(txt_path)
        if npz_path and os.path.exists(npz_path):
            messagebox.showinfo("即将开始步骤 2/2", f"现在将为文件 {os.path.basename(npz_path)} 生成交互式规划地图。")
            visualize_and_pick_stations_html(npz_path)
            messagebox.showinfo("工作流完成", "所有步骤已成功完成！交互式地图已在浏览器中打开。")
        else:
            messagebox.showerror("流程中断", "未能成功生成样条(.npz)文件，无法继续进行地图规划。请检查控制台日志。")
    except Exception as e:
        messagebox.showerror("未预料的异常", f"处理 TXT 文件时发生严重错误: {type(e).__name__}\n\n{e}")


def start_workflow_from_npz():
    """工作流2: 引导用户直接从 NPZ 文件开始进行地图规划。"""
    npz_path = filedialog.askopenfilename(
        title="请选择一个已生成的 .npz 样条文件",
        filetypes=[("NPZ 压缩文件", "*.npz")]
    )
    if not npz_path:
        messagebox.showinfo("操作取消", "用户已取消选择文件。")
        return

    try:
        visualize_and_pick_stations_html(npz_path)
        messagebox.showinfo("工作流完成", "交互式地图已生成并在浏览器中打开！")
    except Exception as e:
        messagebox.showerror("未预料的异常", f"处理 NPZ 文件时发生严重错误: {type(e).__name__}\n\n{e}")


def main():
    """创建并运行主选择GUI。"""
    setup_environment_variables()

    root = tk.Tk()
    root.title("集成化3D轨迹处理与站点规划工具 v3.0 (Dual Output)")
    root.geometry("600x300")
    root.resizable(False, False)

    main_frame = tk.Frame(root, padx=20, pady=20)
    main_frame.pack(expand=True, fill=tk.BOTH)

    title_label = tk.Label(main_frame, text="欢迎使用轨迹规划工具", font=("Arial", 16, "bold"))
    title_label.pack(pady=(0, 20))

    label = tk.Label(main_frame, text="请根据您的数据选择一个工作流程:", font=("Arial", 12))
    label.pack(pady=10)

    btn_style = {
        "font": ("Arial", 12, "bold"),
        "fg": "white",
        "relief": tk.RAISED,
        "borderwidth": 3,
        "width": 40
    }

    btn1 = tk.Button(main_frame, text="1. 从原始TXT文件生成轨迹并规划", command=start_workflow_from_txt,
                     bg="#007BFF", **btn_style)
    btn1.pack(pady=10, ipady=10)

    btn2 = tk.Button(main_frame, text="2. 从现有样条文件(.npz)加载并规划", command=start_workflow_from_npz,
                     bg="#28A745", **btn_style)
    btn2.pack(pady=10, ipady=10)

    root.mainloop()


if __name__ == '__main__':
    main()