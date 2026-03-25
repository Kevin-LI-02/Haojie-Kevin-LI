// ----- FILE: /include/utils/MathTypes.h -----
#pragma once

#include <Eigen/Dense>
#include <vector>

namespace tp {
    using Point = Eigen::Vector3d;
    using Vector = Eigen::Vector3d;
    using PointList = std::vector<Point, Eigen::aligned_allocator<Point>>;
}
