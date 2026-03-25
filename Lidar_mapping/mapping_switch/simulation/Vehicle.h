#ifndef VEHICLE_H
#define VEHICLE_H

#include <random>
#include "MathTypes.h"
#include "simulation/PlanningPoint.h" // 包含指令结构

namespace tp {

    class Vehicle {
    public:
        // --- 状态 ---
        Point position;
        Vector velocity;
        Vector forward_vec;
        double speed;

        // --- 参数 ---
        double position_noise_stddev;

        // --- 构造函数 ---
        Vehicle();
        explicit Vehicle(const Point& initial_pos);

        /**
         * @brief [最终版] 理想执行器模型，接收一个完整的规划指令点。
         * @param target_state 包含位置、速度、朝向等信息的完整目标状态。
         */
        void updateState(const PlanningPoint& target_state);

        void reset();

    private:
        std::mt19937 random_engine_;
        std::normal_distribution<double> normal_dist_;
    };

} // namespace tp

#endif // VEHICLE_H
