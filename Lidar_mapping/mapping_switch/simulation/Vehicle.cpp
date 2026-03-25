#include "simulation/Vehicle.h"
#include <cmath>

namespace tp {

// --- 构造函数 ---
Vehicle::Vehicle()
    : position(Point::Zero()),
      velocity(Vector::Zero()),
      forward_vec(Vector(1.0, 0.0, 0.0)),
      speed(0.0),
      position_noise_stddev(0.01),
      normal_dist_(0.0, 1.0) {
    random_engine_.seed(std::random_device()());
}

Vehicle::Vehicle(const Point& initial_pos)
    : position(initial_pos),
      velocity(Vector::Zero()),
      forward_vec(Vector(1.0, 0.0, 0.0)),
      speed(0.0),
      position_noise_stddev(0.01),
      normal_dist_(0.0, 1.0) {
    random_engine_.seed(std::random_device()());
}

/**
 * @brief [最终版] 理想执行器模型。
 */
void Vehicle::updateState(const PlanningPoint& target_state) {
    // 1. 速度和朝向直接由指令设定
    speed = target_state.speed;
    forward_vec = Vector(std::cos(target_state.heading), std::sin(target_state.heading), 0.0);
    velocity = speed * forward_vec;

    // 2. 位置更新为目标位置（加上噪声）
    Point position_noise(
        normal_dist_(random_engine_) * position_noise_stddev,
        normal_dist_(random_engine_) * position_noise_stddev,
        normal_dist_(random_engine_) * position_noise_stddev
    );
    position = target_state.position + position_noise;
}

void Vehicle::reset() {
    position = Point::Zero();
    velocity = Vector::Zero();
    forward_vec = Vector(1.0, 0.0, 0.0);
    speed = 0.0;
}

} // namespace tp