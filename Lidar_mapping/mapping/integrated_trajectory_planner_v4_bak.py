# ==============================================================================
# 文件名: integrated_trajectory_planner_v4.py
# 描述: 一个集成的3D RTK轨迹处理与交互式站点规划工具。
#
# 版本 4 更新:
# - 支持同时加载和处理多个 TXT 文件。
# - 所有轨迹将在同一张交互式地图上显示，并用不同颜色区分。
# - 新增一个下拉菜单，用于在地图上切换当前正在编辑的轨迹。
# - 导出的 JSON 文件 `trajectories_master.json` 将包含所有轨迹的数据。
# - 导出的站点 CSV 文件将包含所有轨迹的站点，并新增 'trajectory_id' 列。
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
from shapely.geometry import LineString, MultiLineString, box
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
# 模块 1: TXT文件处理与3D样条拟合 (已适配多文件处理)
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
        print(f"➡️ [处理文件: {os.path.basename(input_txt_path)}] 步骤 1/5: 正在读取...")
    try:
        df = pd.read_csv(input_txt_path, sep=r'\s+', engine='python')
    except Exception as e:
        print(f"❌ 读取文件 {os.path.basename(input_txt_path)} 失败: {e}")
        return None, None, None

    required_cols = [lat_col, lon_col, alt_col]
    if not all(col in df.columns for col in required_cols):
        print(f"❌ 文件 {os.path.basename(input_txt_path)} 找不到指定的经纬高列: {required_cols}")
        return None, None, None

    df_clean = df.dropna(subset=required_cols).copy()
    if df_clean.empty:
        print(f"❌ 文件 {os.path.basename(input_txt_path)} 清洗后无有效数据。")
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
        print(f"🌍 步骤 2/5: 坐标已归一化，原点: {origin}")

    x_norm = utm_x - origin[0]
    y_norm = utm_y - origin[1]
    z_norm = alts - origin[2]

    normalized_points = np.vstack((x_norm, y_norm, z_norm)).T
    return normalized_points, origin, f"EPSG:{epsg_code}"


def remove_consecutive_duplicates_3d(points):
    """移除与前一个点坐标完全相同的连续重复3D点。"""
    if len(points) == 0:
        return points

    print(f"🧹 步骤 3/5: 正在移除连续的重复坐标点...")
    kept_points = [points[0]]
    for i in range(1, len(points)):
        if not np.array_equal(points[i], points[i - 1]):
            kept_points.append(points[i])

    discarded_count = len(points) - len(kept_points)
    print(f"ℹ️ 从 {len(points)} 个点中移除了 {discarded_count} 个重复点，剩余 {len(kept_points)} 个点。")
    return np.array(kept_points)


def save_spline_tck_with_origin(filename, tck, origin, epsg):
    """将B样条的tck、坐标原点和EPSG代码保存到.npz文件中。"""
    t, c, k = tck
    np.savez_compressed(filename, t=t, c=c, k=k, origin=origin, epsg=epsg)
    print(f"💾 [独立保存] 样条参数(NPZ)已保存至: {filename}")


# <<< --- 函数已修改，以支持多轨迹 --- >>>
def save_splines_to_json(filename, trajectories_data):
    """
    将多条B样条轨迹的数据保存到一个统一的JSON文件中。
    """
    json_output = {"trajectories": []}

    for traj in trajectories_data:
        t, c, k = traj["tck"]
        control_points_transposed = np.asarray(c).T.tolist()

        traj_json_data = {
            "id": traj["id"],
            "knots": np.asarray(t).tolist(),
            "control_points": control_points_transposed,
            "degree": int(k),
            "origin": np.asarray(traj["origin"]).tolist(),
            "epsg_code": traj["epsg"]
        }
        json_output["trajectories"].append(traj_json_data)

    try:
        with open(filename, 'w') as f:
            json.dump(json_output, f, indent=4)
        print(f"💾 [统一保存] 所有轨迹的参数(JSON)已成功保存至: {filename}")
    except Exception as e:
        print(f"❌ 保存统一JSON文件失败: {e}")


def plot_normalized_spline_fit_3d(points, tck, title="3D Spline Fit"):
    """绘制3D原始点和拟合后的B样条曲线，Z轴视野固定在[-0.5, 0.5]米。"""
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_subplot(111, projection='3d')

    max_points_to_display = 2000
    num_total_points = len(points)
    step = max(1, num_total_points // max_points_to_display)
    points_to_plot = points[::step]
    label_text = f'去重后的点 (抽样显示 {len(points_to_plot)}/{num_total_points} 个)'

    ax.scatter(points_to_plot[:, 0], points_to_plot[:, 1], points_to_plot[:, 2],
               c='red', marker='.', s=10, label=label_text, alpha=0.7)

    u_fine = np.linspace(0, 1, num=1000)
    x_fit, y_fit, z_fit = splev(u_fine, tck)
    ax.plot(x_fit, y_fit, z_fit, 'blue', lw=2, label='B样条拟合曲线')

    ax.set_xlabel('X 相对位移 (m)');
    ax.set_ylabel('Y 相对位移 (m)');
    ax.set_zlabel('Z 相对位移 (m)')
    ax.set_title(title, fontsize=16)
    ax.legend();
    ax.grid(True);
    ax.set_zlim(-0.5, 0.5)

    print("📈 显示3D绘图预览。关闭绘图窗口即可继续。")
    plt.show()


# ==============================================================================
# 模块 2: 地图可视化与站点规划 (已适配多轨迹显示)
# ==============================================================================

def visualize_multiple_trajectories_html(trajectories_data: list):
    """加载一个轨迹数据列表，生成并打开一个统一的交互式Folium地图。"""
    print("\n--- 开始生成多轨迹交互式规划地图 ---")
    if not trajectories_data:
        messagebox.showerror("无数据", "没有可供可视化的轨迹数据。")
        return

    # 1. 准备所有轨迹的WGS84坐标和UTM坐标
    all_latlon_points = []
    all_utm_lines = []
    map_center_lats, map_center_lons = [], []

    print("🗺️ 正在转换所有轨迹坐标以进行显示...")
    for traj in trajectories_data:
        tck, origin, source_utm_epsg = traj["tck"], traj["origin"], traj["epsg"]
        num_points = 10001
        u_fine = np.linspace(0, 1, num=num_points)

        normalized_points = np.array(splev(u_fine, tck)).T
        absolute_utm_points = normalized_points + origin

        all_utm_lines.append(LineString(absolute_utm_points[:, :2]))

        to_wgs84 = Transformer.from_crs(source_utm_epsg, "EPSG:4326", always_xy=True)
        lons, lats = to_wgs84.transform(absolute_utm_points[:, 0], absolute_utm_points[:, 1])

        path_points_latlon = list(zip(lats, lons))
        traj["js_data"] = [{'lat': lat, 'lng': lon, 'u': u} for (lat, lon), u in zip(path_points_latlon, u_fine)]

        map_center_lats.extend(lats)
        map_center_lons.extend(lons)

    # 2. GIS地块分析 (使用所有轨迹的联合缓冲区域)
    gdf_ring1, gdf_ring2 = None, None
    try:
        print("🏠 正在准备从OpenStreetMap获取附近建筑物地块...")
        # 合并所有UTM轨迹线
        multi_line_utm = MultiLineString(all_utm_lines)

        # 创建一个联合缓冲区
        buffer_distance_meters = 50
        combined_buffer_utm = multi_line_utm.buffer(buffer_distance_meters)
        bbox_utm = combined_buffer_utm.bounds

        # 转换边界框用于查询
        source_epsg_for_bbox = trajectories_data[0]["epsg"]  # 假设所有轨迹在相近区域
        to_wgs84_bbox = Transformer.from_crs(source_epsg_for_bbox, "EPSG:4326", always_xy=True)
        west, east = to_wgs84_bbox.transform([bbox_utm[0], bbox_utm[2]], [bbox_utm[1], bbox_utm[3]])
        query_bbox = (max(map_center_lats), min(map_center_lats), max(map_center_lons), min(map_center_lons))
        print(f"✅ 已将查询区域优化为所有轨迹周围 {buffer_distance_meters} 米的联合范围。")

        gdf_buildings = ox.features.features_from_bbox(bbox=query_bbox, tags={"building": True})

        if not gdf_buildings.empty:
            gdf_buildings_utm = gdf_buildings.to_crs(source_epsg_for_bbox)
            indices_ring1 = gdf_buildings_utm.geometry.intersects(combined_buffer_utm)
            gdf_ring1 = gdf_buildings_utm[indices_ring1].to_crs("EPSG:4326")

            if not gdf_ring1.empty:
                ring1_union_geom = gdf_buildings_utm[indices_ring1].unary_union
                indices_touching_ring1 = gdf_buildings_utm.geometry.touches(ring1_union_geom)
                gdf_ring2 = gdf_buildings_utm[indices_touching_ring1 & ~indices_ring1].to_crs("EPSG:4326")
        print("✅ 成功加载并分析了建筑物地块。")
    except Exception as e:
        print(f"⚠️ GIS地块分析失败: {e}。将继续不显示地块。")

    # 3. 创建Folium地图
    map_center = [np.mean(map_center_lats), np.mean(map_center_lons)]
    m = folium.Map(location=map_center, zoom_start=18, tiles=None)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                     attr='Esri', name='Esri Satellite', max_zoom=19).add_to(m)

    if gdf_ring2 is not None: folium.GeoJson(gdf_ring2.to_json(), name='第二圈地块',
                                             style_function=lambda x: {'fillColor': 'gray', 'color': 'white',
                                                                       'weight': 0.5, 'fillOpacity': 0.4}).add_to(m)
    if gdf_ring1 is not None: folium.GeoJson(gdf_ring1.to_json(), name='第一圈地块',
                                             style_function=lambda x: {'fillColor': 'yellow', 'color': 'k', 'weight': 1,
                                                                       'fillOpacity': 0.6}).add_to(m)

    # 4. 绘制所有轨迹
    colors = ['#00FFFF', '#FF00FF', '#00FF00', '#FFA500', '#FF0000',
              '#0000FF']  # Cyan, Magenta, Lime, Orange, Red, Blue
    for i, traj in enumerate(trajectories_data):
        color = colors[i % len(colors)]
        latlon_points = [(p['lat'], p['lng']) for p in traj["js_data"]]
        folium.PolyLine(locations=latlon_points, color=color, weight=5, tooltip=f"轨迹: {traj['id']}").add_to(m)
        folium.Marker(location=latlon_points[0], popup=f"起点: {traj['id']}",
                      icon=folium.Icon(color='green', icon='play')).add_to(m)
        folium.Marker(location=latlon_points[-1], popup=f"终点: {traj['id']}",
                      icon=folium.Icon(color='red', icon='stop')).add_to(m)

    # 5. 注入HTML和JavaScript控制面板 (已更新)
    # 创建轨迹选择器的HTML选项
    trajectory_options_html = "".join(
        [f'<option value="{i}">{traj["id"]}</option>' for i, traj in enumerate(trajectories_data)])

    control_panel_html = f"""
    <div style="position: fixed; top: 10px; right: 10px; z-index:1000; background-color: rgba(255, 255, 255, 0.9); border: 2px solid grey; border-radius: 5px; padding: 10px; font-family: sans-serif; width: 250px;">
        <h4>站点规划控制台</h4>
        <label for="trajectory_selector">当前编辑轨迹:</label>
        <select id="trajectory_selector" style="width: 100%; margin-bottom: 10px;">{trajectory_options_html}</select>
        <hr>
        <label for="u_slider">通过滑块控制:</label>
        <input type="range" id="u_slider" min="0" max="10000" value="0" style="width: 100%;">
        <label for="u_input">手动输入 U 值 (完成后按回车):</label>
        <input type="number" id="u_input" min="0" max="1" step="0.0001" value="0" style="width: 100%; margin-bottom: 10px;">
        <p style="margin: 5px 0;">当前 U 值: <strong id="u_display">0.0000</strong></p>
        <button id="add_station_btn" style="width: 100%; padding: 8px; background-color: #007BFF; color: white; border: none; border-radius: 3px; cursor: pointer; margin-bottom: 10px;">添加站点到当前轨迹</button>
        <hr>
        <button onclick="exportStations()" style="width: 100%; padding: 8px; background-color: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">导出所有站点 (CSV)</button>
        <p id="station_count" style="text-align: center; margin-top: 5px;">已添加: 0 个站点</p>
    </div>
    """

    all_trajectories_js_data = {i: traj["js_data"] for i, traj in enumerate(trajectories_data)}
    trajectory_ids_js = {i: traj["id"] for i, traj in enumerate(trajectories_data)}

    js_logic = f"""
    <script>
        var stationsByTrajectory = {{}};
        var allTrajectories = {json.dumps(all_trajectories_js_data)};
        var trajectoryIds = {json.dumps(trajectory_ids_js)};
        var activeTrajectoryIndex = 0;

        var map_obj = null;
        var previewMarker = null;
        var isInputFocused = false;

        function updatePreviewFromU(u) {{
            let trajectoryPoints = allTrajectories[activeTrajectoryIndex];
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
            let trajectoryPoints = allTrajectories[activeTrajectoryIndex];
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
            let trajectoryPoints = allTrajectories[activeTrajectoryIndex];
            let currentU = parseFloat(document.getElementById('u_input').value);
            if (isNaN(currentU)) return;
            let index = Math.round(currentU * (trajectoryPoints.length - 1));
            let point = trajectoryPoints[index];

            if (!stationsByTrajectory[activeTrajectoryIndex]) {{
                stationsByTrajectory[activeTrajectoryIndex] = [];
            }}

            let defaultName = "站点 " + (stationsByTrajectory[activeTrajectoryIndex].length + 1);
            let stationName = prompt("为轨迹 '" + trajectoryIds[activeTrajectoryIndex] + "' 输入站点名称：", defaultName);
            if (stationName === null || stationName.trim() === '') return;

            stationsByTrajectory[activeTrajectoryIndex].push({{ lat: point.lat, lng: point.lng, name: stationName, u: point.u }});

            L.marker([point.lat, point.lng], {{draggable: false}})
             .addTo(map_obj)
             .bindPopup("<b>" + stationName + "</b><br>轨迹: " + trajectoryIds[activeTrajectoryIndex] + "<br>u = " + point.u.toFixed(4));

            updateTotalStationCount();
        }}

        function updateTotalStationCount() {{
            let totalStations = 0;
            for (const key in stationsByTrajectory) {{
                totalStations += stationsByTrajectory[key].length;
            }}
            document.getElementById('station_count').innerText = "已添加: " + totalStations + " 个站点";
        }}

        function exportStations() {{
            let totalStations = 0;
            for (const key in stationsByTrajectory) {{ totalStations += stationsByTrajectory[key].length; }}
            if (totalStations === 0) {{ alert("您还没有添加任何站点！"); return; }}

            let header = "station_id,trajectory_id,name,latitude,longitude,u_parameter\\n";
            let csvRows = [];
            let globalStationId = 1;

            for (const trajIndex in stationsByTrajectory) {{
                const trajectoryId = trajectoryIds[trajIndex];
                stationsByTrajectory[trajIndex].forEach(station => {{
                    let stationName = '"' + station.name.replace(/"/g, '""') + '"';
                    csvRows.push([globalStationId++, trajectoryId, stationName, station.lat, station.lng, station.u.toFixed(6)].join(','));
                }});
            }}

            let csvContent = "\\uFEFF" + header + csvRows.join("\\n");
            var blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            var link = document.createElement("a");
            var url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", "planned_stations_with_u.csv");
            document.body.appendChild(link); link.click(); document.body.removeChild(link);
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

            document.getElementById('trajectory_selector').addEventListener('change', function() {{
                activeTrajectoryIndex = parseInt(this.value, 10);
                updatePreviewFromU(0); // Reset preview to start of new trajectory
            }});

            updatePreviewFromU(0);
        }}, 500);
    </script>
    """

    m.get_root().html.add_child(branca.element.Element(control_panel_html))
    m.get_root().html.add_child(branca.element.Element(js_logic))
    folium.LayerControl().add_to(m)

    output_dir = os.path.dirname(trajectories_data[0]["npz_path"])
    output_html = os.path.join(output_dir, 'multi_trajectory_planner.html')
    m.save(output_html)
    print(f"\n🎉 多轨迹交互式规划地图已生成: {output_html}")

    try:
        os.startfile(output_html)
        print("✅ 正在默认浏览器中打开地图...")
    except AttributeError:
        os.system(f'{"open" if sys.platform == "darwin" else "xdg-open"} "{output_html}"')
        print(f"✅ 尝试在系统中打开地图: {output_html}")


# ==============================================================================
# 模块 3: 工作流与主GUI (已更新为多文件流程)
# ==============================================================================

def process_multiple_txt_to_spline_data(input_files):
    """主处理流程，处理多个TXT文件，成功时返回轨迹数据列表，失败时返回空列表。"""
    processed_trajectories = []

    for txt_file in input_files:
        print(f"\n--- 开始处理文件: {os.path.basename(txt_file)} ---")
        normalized_points, origin, epsg_code = convert_gps_to_normalized_utm_3d(txt_file, verbose=True)
        if normalized_points is None:
            messagebox.showwarning("预处理失败", f"文件 {os.path.basename(txt_file)} 未能生成归一化UTM坐标，已跳过。")
            continue

        unique_points = remove_consecutive_duplicates_3d(normalized_points)
        if len(unique_points) < 4:
            messagebox.showwarning("数据不足",
                                   f"文件 {os.path.basename(txt_file)} 移除重复点后数据点不足({len(unique_points)})，已跳过。")
            continue

        try:
            spline_tck, _ = splprep(unique_points.T, s=20.0, k=3)
            print("📌 步骤 4/5: 成功拟合3D B样条曲线。")
        except Exception as e:
            messagebox.showwarning("样条拟合错误", f"文件 {os.path.basename(txt_file)} 拟合时发生错误: \n{e}，已跳过。")
            continue

        base_name = os.path.splitext(os.path.basename(txt_file))[0]
        output_dir = os.path.dirname(txt_file)
        npz_name = os.path.join(output_dir, base_name + '_spline.npz')
        save_spline_tck_with_origin(npz_name, spline_tck, origin, epsg_code)

        processed_trajectories.append({
            "id": base_name,
            "tck": spline_tck,
            "origin": origin,
            "epsg": epsg_code,
            "npz_path": npz_name,
            "source_points": unique_points
        })

    if not processed_trajectories:
        return []

    # 统一保存JSON
    output_dir = os.path.dirname(processed_trajectories[0]["npz_path"])
    json_name = os.path.join(output_dir, 'trajectories_master.json')
    save_splines_to_json(json_name, processed_trajectories)

    # 仅对第一个成功处理的文件显示3D预览
    try:
        plt.rcParams['font.family'] = 'SimHei'
        plt.rcParams['axes.unicode_minus'] = False
        first_traj = processed_trajectories[0]
        plot_title = f"文件'{first_traj['id']}'的3D样条拟合预览 (仅显示第一个)"
        plot_normalized_spline_fit_3d(first_traj['source_points'], first_traj['tck'], title=plot_title)
    except Exception as e:
        messagebox.showwarning("绘图警告", f"3D绘图预览失败，但这不影响后续的地图规划。\n错误: {e}")

    return processed_trajectories


def start_workflow_from_txt():
    """工作流1: 引导用户从一个或多个 TXT 文件开始，完成整个流程。"""
    txt_paths = filedialog.askopenfilenames(  # <-- 允许多选
        title="第 1 步: 选择一个或多个RTK TXT数据文件",
        filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
    )
    if not txt_paths:
        messagebox.showinfo("操作取消", "用户已取消选择文件。")
        return

    try:
        trajectories_data = process_multiple_txt_to_spline_data(txt_paths)
        if trajectories_data:
            messagebox.showinfo("步骤 1/2 完成",
                                f"成功处理了 {len(trajectories_data)}/{len(txt_paths)} 个文件。\n\n"
                                f"统一的轨迹数据已保存至 'trajectories_master.json'。\n"
                                f"接下来将自动打开多轨迹地图规划界面。")
            visualize_multiple_trajectories_html(trajectories_data)
            messagebox.showinfo("工作流完成", "所有步骤已成功完成！交互式地图已在浏览器中打开。")
        else:
            messagebox.showerror("流程中断", "未能成功处理任何文件，无法继续进行地图规划。请检查控制台日志。")
    except Exception as e:
        messagebox.showerror("未预料的异常", f"处理 TXT 文件时发生严重错误: {type(e).__name__}\n\n{e}")


def start_workflow_from_npz():
    """工作流2: 引导用户直接从 NPZ 文件开始进行地图规划 (当前版本此功能仅支持单文件)。"""
    messagebox.showinfo("提示", "此功能当前仅支持加载单个 .npz 文件进行可视化。多文件加载请从原始TXT文件开始。")
    npz_path = filedialog.askopenfilename(
        title="请选择一个已生成的 .npz 样条文件",
        filetypes=[("NPZ 压缩文件", "*.npz")]
    )
    if not npz_path:
        messagebox.showinfo("操作取消", "用户已取消选择文件。")
        return

    try:
        # 为了复用，将单个npz文件包装成列表结构
        data = np.load(npz_path)
        single_traj_data = [{
            "id": os.path.splitext(os.path.basename(npz_path))[0],
            "tck": (data['t'], data['c'], data['k']),
            "origin": data['origin'],
            "epsg": str(data['epsg']),
            "npz_path": npz_path
        }]
        visualize_multiple_trajectories_html(single_traj_data)
        messagebox.showinfo("工作流完成", "交互式地图已生成并在浏览器中打开！")
    except Exception as e:
        messagebox.showerror("未预料的异常", f"处理 NPZ 文件时发生严重错误: {type(e).__name__}\n\n{e}")


def main():
    """创建并运行主选择GUI。"""
    setup_environment_variables()

    root = tk.Tk()
    root.title("集成化3D轨迹处理与站点规划工具 v4.0 (Multi-Track)")
    root.geometry("600x300")
    root.resizable(False, False)

    main_frame = tk.Frame(root, padx=20, pady=20)
    main_frame.pack(expand=True, fill=tk.BOTH)

    title_label = tk.Label(main_frame, text="欢迎使用轨迹规划工具", font=("Arial", 16, "bold"))
    title_label.pack(pady=(0, 20))

    label = tk.Label(main_frame, text="请根据您的数据选择一个工作流程:", font=("Arial", 12))
    label.pack(pady=10)

    btn_style = {"font": ("Arial", 12, "bold"), "fg": "white", "relief": tk.RAISED, "borderwidth": 3, "width": 40}

    btn1 = tk.Button(main_frame, text="1. 从原始TXT文件生成轨迹并规划 (支持多选)", command=start_workflow_from_txt,
                     bg="#007BFF", **btn_style)
    btn1.pack(pady=10, ipady=10)

    btn2 = tk.Button(main_frame, text="2. 从现有样条文件(.npz)加载并规划", command=start_workflow_from_npz,
                     bg="#28A745", **btn_style)
    btn2.pack(pady=10, ipady=10)

    root.mainloop()


if __name__ == '__main__':
    main()