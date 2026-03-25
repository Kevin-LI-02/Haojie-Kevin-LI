// /src/utils/JsonParser.cpp

#include "utils/JsonParser.h"
#include "nlohmann/json.hpp"
#include <fstream>
#include <iostream>
#include <vector>

// 使用 nlohmann::json 的命名空间
using json = nlohmann::json;

namespace tp {

bool JsonParser::loadTrajectories(const std::string& filename, std::vector<TrajectoryData>& out_trajectories) {
    // 1. 打开文件
    std::ifstream file_stream(filename);
    if (!file_stream.is_open()) {
        std::cerr << "Error: Could not open file " << filename << std::endl;
        return false;
    }

    // 清空输出容器
    out_trajectories.clear();

    try {
        // 2. 解析 JSON 根数据
        json root_data = json::parse(file_stream);

        // 检查是否存在 "trajectories" 数组
        if (!root_data.contains("trajectories") || !root_data["trajectories"].is_array()) {
            std::cerr << "Error: JSON does not contain a 'trajectories' array." << std::endl;
            return false;
        }

        const auto& traj_array = root_data["trajectories"];
        std::cout << "Found " << traj_array.size() << " trajectories in file." << std::endl;

        // 3. 遍历每一条轨迹数据
        for (const auto& item : traj_array) {
            TrajectoryData traj_data;

            // --- 解析 ID (可选) ---
            if (item.contains("id")) {
                traj_data.id = item["id"].get<std::string>();
            }

            // --- 解析 EPSG Code (可选) ---
            if (item.contains("epsg_code")) {
                traj_data.epsg_code = item["epsg_code"].get<std::string>();
            }

            // --- 解析 Bspline 数据 ---
            // 3.1 Degree
            traj_data.spline.setDegree(item["degree"].get<int>());

            // 3.2 Knots
            traj_data.spline.setKnots(item["knots"].get<std::vector<double>>());

            // 3.3 Control Points
            std::vector<Point> control_points;
            const auto& cp_json_array = item["control_points"];
            control_points.reserve(cp_json_array.size());

            for (const auto& cp_item : cp_json_array) {
                std::vector<double> cp_vec = cp_item.get<std::vector<double>>();
                // 确保数据维度正确 (3维)
                if (cp_vec.size() == 3) {
                    control_points.emplace_back(cp_vec[0], cp_vec[1], cp_vec[2]);
                } else {
                    std::cerr << "Warning: Found a control point with size " << cp_vec.size()
                              << " (expected 3) in trajectory " << traj_data.id << std::endl;
                }
            }
            traj_data.spline.setControlPoints(control_points);

            // --- 解析 Origin ---
            std::vector<double> origin_vec = item["origin"].get<std::vector<double>>();
            if (origin_vec.size() == 3) {
                traj_data.origin = Point(origin_vec[0], origin_vec[1], origin_vec[2]);
            } else {
                std::cerr << "Error: 'origin' field is not a 3D vector in trajectory " << traj_data.id << std::endl;
                continue; // 跳过这条错误的轨迹
            }

            // 将解析好的数据存入列表
            out_trajectories.push_back(traj_data);

            // --- 打印调试信息 ---
            std::cout << "Loaded Trajectory: " << traj_data.id << std::endl;
            std::cout << "  - Degree: " << traj_data.spline.degree() << std::endl;
            std::cout << "  - Control Points: " << traj_data.spline.controlPoints().size() << std::endl;
            std::cout << "  - Origin: [" << traj_data.origin.transpose() << "]" << std::endl;
        }

    } catch (json::parse_error& e) {
        std::cerr << "JSON parse error: " << e.what() << std::endl;
        return false;
    } catch (std::exception& e) {
        std::cerr << "Unexpected error: " << e.what() << std::endl;
        return false;
    }

    return true;
}

} // namespace tp