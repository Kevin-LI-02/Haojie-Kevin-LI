// /src/utils/JsonParser.h (建议修改)
#pragma once
#include "Bspline.h" // 假设这是你的 Bspline 定义文件
#include <string>
#include <vector>

namespace tp {

    // 定义一个结构体来保存单条轨迹的完整信息
    struct TrajectoryData {
        std::string id;          // 对应 JSON 中的 "id"
        Bspline spline;          // 对应 degree, knots, control_points
        Point origin;            // 对应 "origin"
        std::string epsg_code;   // 对应 "epsg_code"
    };

    class JsonParser {
    public:
        // 函数签名修改：输出变为 TrajectoryData 的向量
        static bool loadTrajectories(const std::string& filename, std::vector<TrajectoryData>& out_trajectories);
    };

} // namespace tp
