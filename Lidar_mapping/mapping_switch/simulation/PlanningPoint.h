#ifndef PLANNINGPOINT_H
#define PLANNINGPOINT_H

#include "MathTypes.h" // 引入 Point 和 Vector

namespace tp {

    /**
     * @struct PlanningPoint
     * @brief 一个包含完整运动学和动力学信息的轨迹点，作为规划器输出的核心数据单元。
     */
    struct PlanningPoint {
        // 几何属性
        Point position;      // 3D坐标 (x, y, z)
        double heading;      // 航向角 (弧度)
        double curvature;    // 曲率 (1/m)
        double d_curvature;  // 曲率对弧长的导数 (1/m^2)

        // 运动学与动力学属性
        double arc_length;   // 从路径起点开始的累积弧长 (m)
        double speed;        // 期望速度 (m/s)
        double acceleration; // 期望切向加速度 (m/s^2)
        double relative_time;// 从路径起点开始的相对时间 (s)

        // 默认构造函数，初始化所有值为0
        PlanningPoint() :
            position(Point::Zero()),
            heading(0.0), curvature(0.0), d_curvature(0.0),
            arc_length(0.0), speed(0.0), acceleration(0.0), relative_time(0.0) {}
    };

} // namespace tp

#endif // PLANNINGPOINT_H
