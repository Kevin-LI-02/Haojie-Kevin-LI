#include "simulation/Trajectory.h"
#include <stdexcept>

namespace tp {

    void Trajectory::setPoints(const std::vector<PlanningPoint>& points) {
        points_ = points;
    }

    void Trajectory::addPoint(const PlanningPoint& point) {
        points_.push_back(point);
    }

    void Trajectory::clear() {
        points_.clear();
    }

    const std::vector<PlanningPoint>& Trajectory::getPoints() const {
        return points_;
    }

    std::vector<PlanningPoint>& Trajectory::getPoints_non_const() {
        return points_;
    }

    bool Trajectory::isEmpty() const {
        return points_.empty();
    }

    size_t Trajectory::getPointCount() const {
        return points_.size();
    }

    const PlanningPoint& Trajectory::operator[](size_t index) const {
        return points_.at(index);
    }

    PlanningPoint& Trajectory::operator[](size_t index) {
        return points_.at(index);
    }

    const PlanningPoint& Trajectory::back() const {
        if (isEmpty()) throw std::out_of_range("Trajectory is empty.");
        return points_.back();
    }

    PlanningPoint& Trajectory::back() {
        if (isEmpty()) throw std::out_of_range("Trajectory is empty.");
        return points_.back();
    }

    const PlanningPoint& Trajectory::front() const {
        if (isEmpty()) throw std::out_of_range("Trajectory is empty.");
        return points_.front();
    }

    PlanningPoint& Trajectory::front() {
        if (isEmpty()) throw std::out_of_range("Trajectory is empty.");
        return points_.front();
    }

} // namespace tp